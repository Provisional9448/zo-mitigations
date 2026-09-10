"""Explicit local CLI. Installation does not start these commands."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from . import budget
from .acp import CompletionTracker
from .incidents import IncidentMonitor
from .recovery import WorkerRegistry, process_identity
from .sampling import Sampler
from .transport import command_transport


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def acp_proxy(argv, budget_dir=None):
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        raise ValueError("ACP backend command required after --")
    tracker = CompletionTracker()
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def budget_path(session):
        return Path(budget_dir) / (hashlib.sha256(session.encode()).hexdigest() + ".json")

    def input_loop():
        try:
            for line in sys.stdin:
                try:
                    message = json.loads(line)
                    if not isinstance(message, dict):
                        raise ValueError("JSON-RPC object required")
                    with tracker.lock:
                        tracker.incoming(message)
                        params = message.get("params", {})
                        if budget_dir and message.get("method") == "session/prompt" and params.get("sessionId") and isinstance(params.get("prompt"), list):
                            path = budget_path(params["sessionId"])
                            budget.start(path)
                            timing = budget.snapshot(path)
                            params["prompt"].append({"type": "text", "text":
                                "Advisory run timing: " + json.dumps(timing) +
                                ". Preserve this deadline through steering and compaction. Checkpoint by checkpoint_unix and return by return_by_unix. Include waits and verification. No automatic resumption is provided."})
                        child.stdin.write(json.dumps(message) + "\n")
                        child.stdin.flush()
                except (ValueError, TypeError, KeyError, AttributeError):
                    child.stdin.write(line)
                    child.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        finally:
            child.stdin.close()

    threading.Thread(target=input_loop, daemon=True).start()
    try:
        for line in child.stdout:
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("JSON-RPC object required")
                with tracker.lock:
                    session = tracker.pending.get(message.get("id")) if "method" not in message else None
                    output = tracker.outgoing(message)
                    if budget_dir and session and session not in tracker.pending.values():
                        budget.finish(budget_path(session))
                for item in output:
                    emit(item)
            except (ValueError, TypeError, KeyError, AttributeError):
                sys.stdout.write(line)
                sys.stdout.flush()
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    timer = sub.add_parser("budget", help="Advisory timing; never extends the host limit")
    timer.add_argument("action", choices=["start", "read", "finish"])
    timer.add_argument("--state", required=True)
    monitor = sub.add_parser("monitor", help="Observe Linux metrics and persist a local outbox")
    monitor.add_argument("--state", required=True)
    monitor.add_argument("--once", action="store_true")
    monitor.add_argument("--interval", type=float, default=60)
    monitor.add_argument("--disk-path", default="/")
    monitor.add_argument("--scratch-path", default="/tmp")
    monitor.add_argument("--delivery-argv", help="Opt-in JSON argv array; receives payload on stdin, exit 0 means durable acceptance")
    checkpoint = sub.add_parser("checkpoint", help="Register/update a durable worker checkpoint")
    checkpoint.add_argument("--state", required=True)
    checkpoint.add_argument("--input", required=True, help="JSON record file; '-' reads stdin")
    checkpoint.add_argument("--pid", type=int, help="Capture identity of an existing worker")
    recovery = sub.add_parser("recover", help="Observe registered workers; never launches or replays them")
    recovery.add_argument("--state", required=True)
    recovery.add_argument("--delivery-argv", help="Opt-in JSON argv array for one due notification")
    proxy = sub.add_parser("acp", help="Wrap an explicitly supplied ACP JSONL backend")
    proxy.add_argument("--budget-dir", help="Optional per-session timer state directory")
    proxy.add_argument("backend", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "budget":
        emit({"start": budget.start, "read": budget.snapshot, "finish": budget.finish}[args.action](args.state))
    elif args.command == "monitor":
        if args.interval <= 0:
            parser.error("interval must be positive")
        sampler, observer = Sampler(args.disk_path, args.scratch_path), IncidentMonitor(args.state)
        deliver = command_transport(json.loads(args.delivery_argv)) if args.delivery_argv else None
        while True:
            state = observer.tick(sampler.sample())
            if deliver:
                observer.dispatch_one(deliver)
                state = observer.state
            if args.once:
                emit(state)
                break
            time.sleep(args.interval)
    elif args.command == "checkpoint":
        record = json.load(sys.stdin) if args.input == "-" else json.loads(Path(args.input).read_text())
        if args.pid:
            record["process"] = process_identity(args.pid)
        emit(WorkerRegistry(args.state).checkpoint(record))
    elif args.command == "recover":
        registry = WorkerRegistry(args.state)
        findings = registry.poll()
        delivery = registry.outbox.dispatch_one(command_transport(json.loads(args.delivery_argv))) if args.delivery_argv else None
        emit({"findings": findings, "delivery": delivery, "overflow_count": registry.state.get("overflow_count", 0)})
    elif args.command == "acp":
        return acp_proxy(args.backend, args.budget_dir)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
