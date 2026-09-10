"""Registered worker evidence and durable notifications, without worker replay."""

import copy
import re
import time
from .incidents import IncidentMonitor
from .storage import process_start, runtime_identity, save


def process_identity(pid):
    return {"pid": pid, "start_ticks": process_start(pid), "runtime": runtime_identity()}


def observe_process(expected):
    if not expected or not expected.get("runtime"):
        return "unknown"
    current = runtime_identity()
    if any(k not in current for k in expected["runtime"]):
        return "unknown"
    if any(current[k] != v for k, v in expected["runtime"].items()):
        return "runtime_changed"
    try:
        return "present" if process_start(expected["pid"]) == expected["start_ticks"] else "pid_reused"
    except FileNotFoundError:
        return "absent"
    except (OSError, IndexError, KeyError, ValueError):
        return "unknown"


class WorkerRegistry:
    """A single controller owns both checkpoint writes and recovery polling."""

    def __init__(self, path):
        self.outbox = IncidentMonitor(path, limits={})
        self.state = self.outbox.state
        self.state.setdefault("tasks", {})
        self.path = path

    def checkpoint(self, record):
        task_id = record.get("task_id", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", task_id):
            raise ValueError("Invalid task ID")
        if not isinstance(record.get("attempt"), int) or isinstance(record["attempt"], bool) or record["attempt"] < 1:
            raise ValueError("Positive attempt required")
        for key in ("objective", "authority", "next_step"):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError(f"Nonempty {key} required")
        if record.get("terminal") not in (None, "succeeded", "failed", "cancelled"):
            raise ValueError("Invalid terminal status")
        old = self.state["tasks"].get(task_id)
        if old and record["attempt"] < old["attempt"]:
            raise ValueError("Cannot replace a newer attempt")
        if old and record["attempt"] == old["attempt"] and old.get("terminal") and record.get("terminal") != old["terminal"]:
            raise ValueError("Terminal evidence is immutable for this attempt")
        saved = copy.deepcopy(record)
        saved["notifications"] = old.get("notifications", []) if old and record["attempt"] == old["attempt"] else []
        saved["updated_at"] = time.time()
        self.state["tasks"][task_id] = saved
        save(self.path, self.state)
        return copy.deepcopy(saved)

    def poll(self, *, observer=observe_process, now=None):
        now = time.time() if now is None else now
        findings = []
        for task_id, task in self.state["tasks"].items():
            status = observer(task.get("process")) if not task.get("terminal") else "terminal_recorded"
            if status == "present":
                continue
            kind = "worker_terminal" if task.get("terminal") else "worker_reconciliation_needed"
            findings.append({"task_id": task_id, "attempt": task["attempt"], "observation": status,
                             "terminal": task.get("terminal"), "next_step": task["next_step"]})
            if kind in task["notifications"]:
                continue
            prior_overflow = self.state.get("overflow_count", 0)
            self.outbox.event(kind, now, {"worker_task_id": task_id, "attempt": task["attempt"],
                "observation": status, "checkpoint": copy.deepcopy(task),
                "instruction": "Reconcile current effects and artifacts within recorded authority. Terminal exit is not business acceptance. Do not blindly replay."})
            if self.state.get("overflow_count", 0) == prior_overflow:
                payload = self.state["events"][-1]["payload"]
                if task.get("conversation_id"):
                    payload["conversation_id"] = task["conversation_id"]
                task["notifications"].append(kind)
        save(self.path, self.state)
        return findings
