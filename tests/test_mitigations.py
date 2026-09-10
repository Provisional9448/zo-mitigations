import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from zo_mitigations import budget
from zo_mitigations.acp import CompletionTracker
from zo_mitigations.incidents import IncidentMonitor
from zo_mitigations.recovery import WorkerRegistry, observe_process, process_identity
from zo_mitigations.storage import read, save
from zo_mitigations.transport import command_transport


IDENTITY = {"boot_id": "synthetic-boot", "pid1_start_ticks": "1"}


class StoredTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mitigations-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.json"


class BudgetTests(StoredTest):
    def test_allowance_and_steering_preserve_original_deadline(self):
        first = budget.start(self.path, wall=1000, monotonic=50, identity=IDENTITY)
        second = budget.start(self.path, wall=2000, monotonic=1050, identity=IDENTITY)
        self.assertEqual(first, second)
        status = budget.snapshot(self.path, monotonic=150, identity=IDENTITY)
        self.assertEqual(status["remaining_seconds"], 3380)
        self.assertEqual(status["checkpoint_in_seconds"], 2780)

    def test_earlier_start_and_clock_changes(self):
        budget.start(self.path, wall=1000, monotonic=50, identity=IDENTITY, known_started_at=500)
        self.assertEqual(budget.snapshot(self.path, monotonic=60, identity=IDENTITY)["deadline_unix"], 4100)
        self.assertFalse(budget.snapshot(self.path, monotonic=49, identity=IDENTITY)["available"])

    def test_reboot_does_not_reset_or_claim_valid_time(self):
        first = budget.start(self.path, wall=1000, monotonic=50, identity=IDENTITY)
        new = {**IDENTITY, "pid1_start_ticks": "2"}
        result = budget.snapshot(self.path, monotonic=1, identity=new)
        self.assertFalse(result["available"])
        self.assertEqual(result["deadline_unix"], first["started_at"] + 3600)
        self.assertEqual(budget.start(self.path, identity=new)["run_id"], first["run_id"])

    def test_end_freezes_time_and_next_prompt_can_start(self):
        first = budget.start(self.path, wall=1000, monotonic=50, identity=IDENTITY)
        budget.finish(self.path, monotonic=60)
        self.assertEqual(budget.snapshot(self.path, monotonic=200, identity=IDENTITY)["elapsed_seconds"], 130)
        second = budget.start(self.path, wall=1100, monotonic=150, identity=IDENTITY)
        self.assertNotEqual(first["run_id"], second["run_id"])


class IncidentTests(StoredTest):
    def monitor(self, **kwargs):
        return IncidentMonitor(self.path, limits={"cpu_pct": 90}, **kwargs)

    def test_baseline_and_monitor_restart_are_silent(self):
        self.monitor().tick({}, identity=IDENTITY, now=0)
        state = self.monitor().tick({}, identity=IDENTITY, now=60)
        self.assertEqual(state["events"], [])

    def test_epoch_and_gap_are_distinct(self):
        observer = self.monitor()
        observer.tick({}, identity=IDENTITY, now=0)
        state = observer.tick({}, identity={**IDENTITY, "boot_id": "synthetic-next"}, now=500)
        self.assertEqual(state["events"][-1]["payload"]["kind"], "runtime_epoch_changed")
        state = observer.tick({}, identity={}, now=800)
        self.assertEqual(state["events"][-1]["payload"]["kind"], "measurement_gap")
        self.assertEqual(state["missing_identity_signals"], ["boot_id", "pid1_start_ticks"])

    def test_sustained_pressure_recovery_and_cooldown(self):
        observer = self.monitor(sustained=120, recovery=60, cooldown=600)
        for now in (0, 60, 120, 180):
            observer.tick({"cpu_pct": 95}, identity=IDENTITY, now=now)
        self.assertEqual(len(observer.state["events"]), 1)
        for now in (240, 300):
            observer.tick({"cpu_pct": 80}, identity=IDENTITY, now=now)
        self.assertFalse(observer.state["signals"]["cpu_pct"]["active"])
        for now in range(360, 721, 60):
            observer.tick({"cpu_pct": 95}, identity=IDENTITY, now=now)
        self.assertEqual(len(observer.state["events"]), 2)

    def test_missing_or_nonfinite_metric_breaks_pressure_continuity(self):
        observer = self.monitor(sustained=120)
        for now, value in ((0, 95), (60, float("nan")), (120, 95), (180, 95)):
            observer.tick({"cpu_pct": value}, identity=IDENTITY, now=now)
        self.assertEqual(observer.state["events"], [])
        observer.tick({"cpu_pct": True}, identity=IDENTITY, now=240)
        self.assertEqual(observer.state["missing_signals"], ["cpu_pct"])

    def test_retry_identity_payload_survives_restart_and_exhaustion(self):
        observer = self.monitor(max_attempts=2)
        observer.event("synthetic", 0, {"sample": 1})
        save(self.path, observer.state)
        seen = []

        def fail(payload):
            seen.append(payload.copy())
            payload["task_id"] = "callback-mutation"
            return False

        observer.dispatch_one(fail, now=0)
        self.assertIsNone(observer.dispatch_one(fail, now=59))
        observer = self.monitor(max_attempts=2)
        observer.dispatch_one(fail, now=60)
        self.assertEqual(seen[0], seen[1])
        self.assertTrue(observer.state["events"][0]["retry_exhausted"])
        self.assertIsNone(observer.dispatch_one(fail, now=1000))

    def test_acceptance_is_persisted_and_not_redispatched(self):
        observer = self.monitor()
        observer.event("synthetic", 0, {})
        observer.dispatch_one(lambda payload: True, now=0)
        self.assertIsNone(self.monitor().dispatch_one(lambda payload: self.fail("duplicate"), now=100))

    def test_attempt_is_persisted_before_callback(self):
        observer = self.monitor()
        observer.event("synthetic", 0, {})

        def inspect(payload):
            saved = read(self.path)["events"][0]
            self.assertEqual(saved["attempts"], 1)
            self.assertEqual(saved["payload"], payload)
            return True

        observer.dispatch_one(inspect, now=0)

    def test_overflow_is_visible_and_bounded(self):
        observer = self.monitor(capacity=2)
        for _ in range(5):
            observer.event("synthetic", 0, {})
        observer.tick({}, identity=IDENTITY, now=0)
        self.assertEqual(len(observer.state["events"]), 2)
        self.assertEqual(read(self.path)["overflow_count"], 3)

    def test_corrupt_state_is_not_silently_replaced(self):
        save(self.path, {"version": 999})
        with self.assertRaises(ValueError):
            self.monitor()


class RecoveryTests(StoredTest):
    def record(self, **kwargs):
        return {"task_id": "sample-task", "attempt": 1, "objective": "Review synthetic artifact",
                "authority": "Read-only synthetic review", "next_step": "Inspect retained evidence", **kwargs}

    def test_live_process_identity_and_pid_reuse(self):
        identity = process_identity(os.getpid())
        self.assertEqual(observe_process(identity), "present")
        self.assertEqual(observe_process({**identity, "start_ticks": "impossible"}), "pid_reused")

    def test_missing_worker_emits_once_without_replay(self):
        registry = WorkerRegistry(self.path)
        registry.checkpoint(self.record(conversation_id="synthetic-chat"))
        registry.poll(observer=lambda _: "absent", now=0)
        registry = WorkerRegistry(self.path)
        registry.poll(observer=lambda _: "absent", now=60)
        self.assertEqual(len(registry.state["events"]), 1)
        self.assertEqual(registry.state["events"][0]["payload"]["conversation_id"], "synthetic-chat")
        self.assertIsNone(registry.state["tasks"]["sample-task"].get("terminal"))

    def test_terminal_saved_before_notification_and_separate_from_reconciliation(self):
        registry = WorkerRegistry(self.path)
        registry.checkpoint(self.record())
        registry.poll(observer=lambda _: "unknown", now=0)
        registry.checkpoint(self.record(terminal="failed"))
        self.assertEqual(read(self.path)["tasks"]["sample-task"]["terminal"], "failed")
        registry.poll(now=60)
        self.assertEqual(len(registry.state["events"]), 2)
        with self.assertRaises(ValueError):
            registry.checkpoint(self.record())

    def test_live_worker_does_not_request_reconciliation(self):
        registry = WorkerRegistry(self.path)
        registry.checkpoint(self.record())
        self.assertEqual(registry.poll(observer=lambda _: "present"), [])
        self.assertEqual(registry.state["events"], [])


class ACPTests(unittest.TestCase):
    def prompt(self, tracker, identifier=1):
        tracker.incoming({"id": identifier, "method": "session/prompt", "params": {"sessionId": "synthetic-session"}})

    def result(self, identifier=1, stop="end_turn"):
        return {"id": identifier, "result": {"stopReason": stop}}

    def test_usage_is_not_completion(self):
        tracker = CompletionTracker()
        self.prompt(tracker)
        event = {"method": "session/update", "params": {"sessionId": "synthetic-session", "update": {"sessionUpdate": "usage_update"}}}
        self.assertEqual(tracker.outgoing(event), [event])
        self.assertEqual(len(tracker.outgoing(self.result())), 2)

    def test_cancellation_error_and_unmatched_response_never_succeed(self):
        for response in (self.result(stop="cancelled"), {"id": 1, "error": {"code": -1}}, self.result(identifier=2)):
            tracker = CompletionTracker()
            self.prompt(tracker)
            self.assertEqual(tracker.outgoing(response), [response])

    def test_steering_waits_until_last_pending_prompt(self):
        tracker = CompletionTracker()
        self.prompt(tracker, 1)
        self.prompt(tracker, 2)
        self.assertEqual(len(tracker.outgoing(self.result(1))), 1)
        self.assertEqual(len(tracker.outgoing(self.result(2))), 2)

    def test_native_terminal_not_duplicated_and_later_turn_works(self):
        tracker = CompletionTracker()
        self.prompt(tracker)
        tracker.outgoing({"method": "session/update", "params": {"sessionId": "synthetic-session", "update": {"sessionUpdate": "end_turn"}}})
        self.assertEqual(len(tracker.outgoing(self.result())), 1)
        self.prompt(tracker, 2)
        self.assertEqual(len(tracker.outgoing(self.result(2))), 2)


class CLITests(StoredTest):
    def test_offline_monitor_command(self):
        result = subprocess.run([sys.executable, "-m", "zo_mitigations", "monitor", "--once", "--state", str(self.path)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["events"], [])

    def test_acp_wrapper_runs_synthetic_backend_and_finishes_budget(self):
        backend = "import sys,json; m=json.loads(sys.stdin.readline()); print(json.dumps({'id':m['id'],'result':{'stopReason':'end_turn'}}),flush=True)"
        prompt = {"id": 1, "method": "session/prompt", "params": {"sessionId": "synthetic-session", "prompt": []}}
        result = subprocess.run([sys.executable, "-m", "zo_mitigations", "acp", "--budget-dir", self.temp.name, "--", sys.executable, "-c", backend], input=json.dumps(prompt) + "\n", text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(output[0]["params"]["update"]["sessionUpdate"], "end_turn")
        self.assertEqual(output[1]["id"], 1)
        self.assertFalse(read(next(Path(self.temp.name).glob("*.json")))["active"])

    def test_explicit_transport_and_timeout(self):
        deliver = command_transport([sys.executable, "-c", "import json,sys; assert json.load(sys.stdin)['task_id']=='synthetic'"])
        self.assertTrue(deliver({"task_id": "synthetic"}))
        with self.assertRaises(subprocess.TimeoutExpired):
            command_transport([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.05)({})


if __name__ == "__main__":
    unittest.main()
