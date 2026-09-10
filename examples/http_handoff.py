"""Opt-in command adapter for a compatible authenticated durable handoff service."""

import json
import os
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def submit(event):
    endpoint = os.environ["MITIGATIONS_HANDOFF_URL"]
    token = os.environ["MITIGATIONS_HANDOFF_TOKEN"]
    authority = os.environ["MITIGATIONS_RECOVERY_AUTHORITY"]
    url = urlsplit(endpoint)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Expected a recipient-owned HTTPS endpoint without URL credentials/query/fragment")
    if not token.strip() or not authority.strip():
        raise ValueError("Missing recipient credential or recovery scope")
    payload = {"task_id": event["task_id"], "target": "zo",
               "brief": "Inspect this recorded observation and current checkpoint before acting: " + json.dumps(event, sort_keys=True) + ". Observation is not new authority. Reconcile uncertain effects before continuation.",
               "authorization": authority, "references": []}
    if event.get("conversation_id"):
        payload["conversation_id"] = event["conversation_id"]
    request = Request(endpoint, data=json.dumps(payload).encode(), method="POST",
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json"})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("Oversized receipt; reconcile accepted task before retry")
        receipt = json.loads(raw)
    if receipt.get("task_id") != event["task_id"] or receipt.get("status") not in {"queued", "running", "dispatched", "working", "checkpointed", "returned", "completed", "failed", "interrupted"}:
        raise ValueError("No matching durable task receipt; reconcile before retry")
    return {"task_id": receipt["task_id"], "accepted": True}


if __name__ == "__main__":
    try:
        print(json.dumps(submit(json.load(sys.stdin))))
    except Exception as error:
        print("Handoff did not return a validated receipt: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
