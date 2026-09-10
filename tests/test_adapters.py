import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


def load_example(name):
    path = Path(__file__).resolve().parents[1] / "examples" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inbox = load_example("local_inbox")
handoff = load_example("http_handoff")


class AdapterTests(unittest.TestCase):
    def test_inbox_retry_and_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "inbox"
            event = {"task_id": "synthetic-task", "facts": {"value": 1}}
            first = inbox.accept(directory, event)
            self.assertEqual(inbox.accept(directory, event), first)
            self.assertFalse(first["agent_started"])
            files = list(directory.iterdir())
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                inbox.accept(directory, {**event, "facts": {"value": 2}})
            self.assertEqual(json.loads(files[0].read_text()), event)

    def test_inbox_task_id_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "inbox"
            inbox.accept(directory, {"task_id": "../../synthetic-task"})
            self.assertEqual(len(list(directory.iterdir())), 1)
            self.assertEqual(len(list(Path(temporary).iterdir())), 1)

    def submit_with_receipt(self, receipt):
        response = io.BytesIO(json.dumps(receipt).encode())
        opener = Mock()
        opener.open.return_value = response
        environment = {"MITIGATIONS_HANDOFF_URL": "https://example.invalid/handoff/tasks",
                       "MITIGATIONS_HANDOFF_TOKEN": "synthetic-credential",
                       "MITIGATIONS_RECOVERY_AUTHORITY": "Inspect synthetic evidence only"}
        with patch.dict(handoff.os.environ, environment), patch.object(handoff, "build_opener", return_value=opener):
            result = handoff.submit({"task_id": "synthetic-task", "conversation_id": "synthetic-chat"})
        request = opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)["conversation_id"], "synthetic-chat")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 15)
        return result

    def test_matching_receipt(self):
        self.assertEqual(self.submit_with_receipt({"task_id": "synthetic-task", "status": "queued"}),
                         {"task_id": "synthetic-task", "accepted": True})

    def test_wrong_identity_or_status_refused(self):
        for receipt in ({"task_id": "other-task", "status": "queued"},
                        {"task_id": "synthetic-task", "status": "unknown"}):
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                self.submit_with_receipt(receipt)

    def test_redirect_handler_refuses_redirect_without_network(self):
        request = handoff.Request("https://example.invalid/handoff/tasks", data=b"{}",
                                  headers={"Authorization": "Bearer synthetic-credential"})
        handler = handoff.NoRedirect()
        handler.parent = Mock()
        self.assertIsNone(handler.http_error_302(request, io.BytesIO(), 302, "Found",
                                                {"location": "https://other.invalid/collect"}))
        handler.parent.open.assert_not_called()

    def test_unsafe_url_refused_before_transport(self):
        for endpoint in ("http://example.invalid/tasks", "https://person@example.invalid/tasks",
                         "https://example.invalid/tasks?token=synthetic", "https://example.invalid/tasks#fragment"):
            environment = {"MITIGATIONS_HANDOFF_URL": endpoint,
                           "MITIGATIONS_HANDOFF_TOKEN": "synthetic-credential",
                           "MITIGATIONS_RECOVERY_AUTHORITY": "Synthetic scope"}
            with self.subTest(endpoint=endpoint), patch.dict(handoff.os.environ, environment), patch.object(handoff, "build_opener") as transport:
                with self.assertRaises(ValueError):
                    handoff.submit({"task_id": "synthetic-task"})
                transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
