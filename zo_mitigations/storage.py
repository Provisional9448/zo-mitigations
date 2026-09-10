"""Atomic private JSON storage for a single owning controller."""

import json
import os
from pathlib import Path
import tempfile


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, allow_nan=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read(path, version=1):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or value.get("version") != version:
        raise ValueError("Unsupported state schema")
    return value


def runtime_identity():
    result = {}
    try:
        result["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        pass
    try:
        result["pid1_start_ticks"] = process_start(1)
    except (OSError, IndexError):
        pass
    return result


def process_start(pid):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        raise ValueError("A positive PID is required")
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
