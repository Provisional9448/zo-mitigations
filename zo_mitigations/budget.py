"""Advisory monotonic turn timing; this never cancels or resumes work."""

import time
import uuid
from .storage import read, runtime_identity, save


def start(path, *, wall=None, monotonic=None, identity=None, limit=3600,
          allowance=120, known_started_at=None):
    if limit <= 600 or not 0 <= allowance < limit:
        raise ValueError("Limit must exceed 600 seconds; allowance must be within limit")
    wall = time.time() if wall is None else wall
    monotonic = time.monotonic() if monotonic is None else monotonic
    identity = runtime_identity() if identity is None else identity
    try:
        previous = read(path)
    except FileNotFoundError:
        previous = None
    if previous and previous["active"]:
        return previous
    started = wall - allowance
    if known_started_at is not None:
        started = min(started, known_started_at)
    state = {"version": 1, "run_id": uuid.uuid4().hex, "active": True,
             "received_monotonic": monotonic, "initial_elapsed": wall - started,
             "started_at": started, "limit": limit, "identity": identity,
             "host_deadline_verified": False}
    save(path, state)
    return state


def snapshot(path, *, monotonic=None, identity=None):
    state = read(path)
    identity = runtime_identity() if identity is None else identity
    monotonic = time.monotonic() if monotonic is None else monotonic
    deadline = state["started_at"] + state["limit"]
    result = {"run_id": state["run_id"], "active": state["active"],
              "deadline_unix": deadline, "checkpoint_unix": deadline - 600,
              "return_by_unix": deadline - 300, "host_deadline_verified": False}
    if not state["identity"] or any(identity.get(k) != v for k, v in state["identity"].items()):
        return {**result, "available": False, "reason": "Runtime identity changed or unavailable; retain last deadline"}
    current = state.get("ended_monotonic", monotonic)
    if current < state["received_monotonic"]:
        return {**result, "available": False, "reason": "Monotonic clock invalid; retain last deadline"}
    elapsed = current - state["received_monotonic"] + state["initial_elapsed"]
    return {**result, "available": True, "elapsed_seconds": elapsed,
            "remaining_seconds": max(0, state["limit"] - elapsed),
            "checkpoint_in_seconds": max(0, state["limit"] - 600 - elapsed),
            "return_in_seconds": max(0, state["limit"] - 300 - elapsed)}


def finish(path, *, monotonic=None):
    state = read(path)
    if state["active"]:
        state.update(active=False, ended_monotonic=time.monotonic() if monotonic is None else monotonic)
        save(path, state)
    return state
