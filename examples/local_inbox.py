"""Durable offline receiver. No agent wake-up or outbound request."""

import hashlib
import json
import os
from pathlib import Path
import sys


def accept(directory, payload):
    identifier = payload.get("task_id")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Missing task ID")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (hashlib.sha256(identifier.encode()).hexdigest() + ".json")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError("Conflicting or incomplete stored payload; reconcile before retry")
    else:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return {"task_id": identifier, "status": "accepted", "agent_started": False}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: local_inbox.py PRIVATE_DIRECTORY")
    print(json.dumps(accept(sys.argv[1], json.load(sys.stdin))))
