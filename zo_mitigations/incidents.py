"""Persistent restart/pressure evidence and bounded at-least-once delivery."""

import copy
import math
import time
import uuid
from .storage import read, runtime_identity, save


class IncidentMonitor:
    """One owning process. The caller supplies bounded, idempotent delivery."""

    def __init__(self, path, *, limits=None, sustained=300, recovery=180,
                 cooldown=3600, max_gap=180, max_attempts=6, capacity=24):
        if min(sustained, recovery, cooldown, max_gap) < 0 or min(max_attempts, capacity) < 1:
            raise ValueError("Invalid monitoring bounds")
        self.path = path
        self.limits = dict(limits if limits is not None else {"cpu_pct": 90, "ram_pct": 90, "disk_pct": 95, "tmp_pct": 90})
        self.sustained, self.recovery, self.cooldown = sustained, recovery, cooldown
        self.max_gap, self.max_attempts, self.capacity = max_gap, max_attempts, capacity
        try:
            self.state = read(path)
        except FileNotFoundError:
            self.state = {"version": 1, "events": [], "signals": {}}

    def event(self, kind, now, facts):
        pending = [e for e in self.state["events"] if "delivered_at" not in e]
        if len(pending) >= self.capacity:
            self.state["overflow_count"] = self.state.get("overflow_count", 0) + 1
            return
        completed = [e for e in self.state["events"] if "delivered_at" in e]
        self.state["events"] = completed[-8:] + pending + [{
            "payload": {"task_id": "incident-" + uuid.uuid4().hex, "kind": kind,
                        "observed_at": now, "facts": copy.deepcopy(facts)},
            "attempts": 0, "next_attempt": now}]

    def tick(self, metrics, *, identity=None, now=None):
        now = time.time() if now is None else now
        identity = runtime_identity() if identity is None else identity
        metrics = {k: v for k, v in metrics.items() if k in self.limits
                   and isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) and v >= 0}
        previous = self.state.get("identity", {})
        changed = sorted(k for k in identity if k in previous and previous[k] != identity[k])
        last = self.state.get("last_sample")
        gap = last is not None and (now - last > self.max_gap or now < last)
        if changed:
            self.event("runtime_epoch_changed", now, {"changed_signals": changed,
                       "previous_identity": previous, "identity": identity, "metrics": metrics})
        elif gap:
            self.event("measurement_gap", now, {"gap_seconds": now - last, "metrics": metrics})
        self.state["identity"] = {**previous, **identity}
        self.state["missing_identity_signals"] = sorted({"boot_id", "pid1_start_ticks"} - identity.keys())
        for name, threshold in self.limits.items():
            signal = self.state["signals"].setdefault(name, {"active": False})
            if gap or changed or name not in metrics:
                signal.pop("high_since", None)
                signal.pop("low_since", None)
            if name not in metrics:
                continue
            value = metrics[name]
            if value >= threshold:
                signal.pop("low_since", None)
                signal.setdefault("high_since", now)
                if not signal["active"] and now - signal["high_since"] >= self.sustained and now >= signal.get("next_allowed", 0):
                    self.event("sustained_resource_pressure", now, {"signal": name, "threshold": threshold, "metrics": metrics})
                    signal.update(active=True, next_allowed=now + self.cooldown)
            elif value <= threshold - 5:
                signal.pop("high_since", None)
                signal.setdefault("low_since", now)
                if signal["active"] and now - signal["low_since"] >= self.recovery:
                    signal["active"] = False
            else:
                signal.pop("high_since", None)
                signal.pop("low_since", None)
        self.state.update(last_sample=now, latest_metrics=metrics,
                          missing_signals=sorted(set(self.limits) - metrics.keys()))
        save(self.path, self.state)
        return copy.deepcopy(self.state)

    def dispatch_one(self, deliver, *, now=None):
        """Callback returns True only after durable receiver acceptance of task_id.

        A crash after receiver acceptance may retry the same payload. Receiver
        deduplication is required; an acceptance is not workflow completion.
        """
        now = time.time() if now is None else now
        due = [e for e in self.state["events"] if "delivered_at" not in e
               and e["attempts"] < self.max_attempts and e["next_attempt"] <= now]
        if not due:
            return None
        event = due[0]
        event["attempts"] += 1
        event["next_attempt"] = now + min(3600, 60 * 2 ** (event["attempts"] - 1))
        if event["attempts"] == self.max_attempts:
            event["retry_exhausted"] = True
        save(self.path, self.state)
        try:
            accepted = deliver(copy.deepcopy(event["payload"])) is True
        except Exception as error:
            accepted = False
            event["last_error_type"] = type(error).__name__
        if accepted:
            event["delivered_at"] = now
            event.pop("retry_exhausted", None)
            event.pop("last_error_type", None)
        save(self.path, self.state)
        return copy.deepcopy(event)
