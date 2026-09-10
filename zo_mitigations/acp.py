"""Minimal completion guard for bidirectional ACP JSON-RPC adapters."""

import threading


class CompletionTracker:
    def __init__(self):
        self.pending = {}
        self.closed = set()
        self.lock = threading.RLock()

    def incoming(self, message):
        with self.lock:
            if message.get("method") == "session/prompt" and "id" in message:
                session = message.get("params", {}).get("sessionId")
                if session:
                    if session not in self.pending.values():
                        self.closed.discard(session)
                    self.pending[message["id"]] = session

    def outgoing(self, message):
        with self.lock:
            params = message.get("params", {})
            if message.get("method") == "session/update" and params.get("update", {}).get("sessionUpdate") in {"end_turn", "error"}:
                self.closed.add(params.get("sessionId"))
            session = self.pending.pop(message.get("id"), None) if "method" not in message else None
            if not session or session in self.pending.values():
                return [message]
            result = message.get("result")
            synthesize = session not in self.closed and "error" not in message and isinstance(result, dict) and result.get("stopReason") == "end_turn"
            self.closed.discard(session)
            if not synthesize:
                return [message]
            return [{"jsonrpc": "2.0", "method": "session/update", "params": {
                "sessionId": session, "update": {"sessionUpdate": "end_turn"}}}, message]
