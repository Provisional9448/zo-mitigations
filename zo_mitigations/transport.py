"""Explicit recipient-supplied command transport, never a shell command."""

import json
import subprocess


def command_transport(argv, timeout=20):
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError("Delivery argv must be a nonempty JSON array of strings")
    if timeout <= 0:
        raise ValueError("Positive timeout required")

    def deliver(payload):
        result = subprocess.run(argv, input=json.dumps(payload), text=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=False, shell=False)
        return result.returncode == 0
    return deliver
