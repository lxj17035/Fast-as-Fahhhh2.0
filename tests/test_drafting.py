import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.config import load_env
from backend.drafting import DraftService, OpenAIExtractor, ProviderError
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.store import Store


def valid_output():
    return {"summary": "20 event shirts", "clientName": "Demo Events", "clientAddress": None,
            "items": [{"description": "Printed T-shirts", "quantity": 20}], "missingInformation": []}


def response(value=None):
    return {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(value if value is not None else valid_output())}]}]}


class DraftingTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.settings = SettingsService(self.store)
        self.quotes = QuotationService(self.store, self.settings)
        with self.store.transaction():
            self.store.put("enquiries", "demo", {"id": "demo", "text": "Need 20 printed T-shirts",
                           "source": "telegram", "chatId": "test-chat", "clientId": "demo-client"})
        self.transport = Mock(return_value=response())
        self.extractor = OpenAIExtractor("fake-test-key", "test-model", self.transport)
        self.service = DraftService(self.store, self.settings, self.quotes, self.extractor)

    def test_structured_request_and_prices_stay_blank(self):
        draft = self.service.create("demo")
        self.assertEqual(draft["draftMode"], "ai")
        self.assertEqual(draft["client"]["name"], "Demo Events")
        self.assertIsNone(draft["items"][0]["unitPrice"])
        self.assertIsNone(draft["total"])
        payload = self.transport.call_args.args[0]
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertFalse(payload["store"])
        self.assertNotIn("tools", payload)
        self.assertIn("businessContext", payload["input"])

    def test_unknown_quantity_preserved(self):
        value = valid_output()
        value["items"][0]["quantity"] = None
        self.transport.return_value = response(value)
        self.assertIsNone(self.service.create("demo")["items"][0]["quantity"])

    def test_unexpected_prices_and_bad_fields_fall_back(self):
        for mutate in [lambda v: v["items"][0].update(unitPrice=50),
                       lambda v: v.update(summary=None),
                       lambda v: v["items"][0].update(quantity=-1)]:
            value = valid_output()
            mutate(value)
            self.transport.return_value = response(value)
            with self.assertRaises(ProviderError):
                self.extractor.extract("message", {})

    def test_missing_key_never_calls_network(self):
        self.service.extractor = OpenAIExtractor("", "", self.transport)
        draft = self.service.create("demo")
        self.assertEqual(draft["draftMode"], "manual")
        self.assertIn("not configured", draft["draftError"])
        self.transport.assert_not_called()
        self.assertEqual(self.store.get("enquiries", "demo")["status"], "needs_review")

    def test_manual_choice_bypasses_provider(self):
        draft = self.service.create("demo", manual=True)
        self.assertEqual(draft["draftMode"], "manual")
        self.transport.assert_not_called()

    def test_provider_timeout_malformed_and_refusal_are_recoverable(self):
        cases = [TimeoutError("secret raw error"), {"status": "incomplete"},
                 {"status": "completed", "output": []},
                 {"status": "completed", "output": [{"type": "message", "content": [
                     {"type": "refusal", "refusal": "raw provider detail"}]}]},
                 {"status": "completed", "output": [None]}]
        for result in cases:
            if isinstance(result, Exception):
                self.transport.side_effect = result
            else:
                self.transport.side_effect = None
                self.transport.return_value = result
            with self.assertRaises(ProviderError) as failure:
                self.extractor.extract("message", {})
            self.assertNotIn("secret", str(failure.exception))
            self.assertNotIn("raw provider", str(failure.exception))

    def test_failed_provider_persists_manual_draft_and_original_message(self):
        self.transport.side_effect = TimeoutError()
        draft = self.service.create("demo")
        self.assertEqual(draft["draftMode"], "manual")
        self.assertEqual(draft["items"], [])
        self.assertIn("20 printed", draft["summary"])
        self.assertEqual(len(self.store.list("activity")), 1)

    def test_repeated_draft_request_does_not_overwrite_manual_prices(self):
        first = self.service.create("demo")
        self.quotes.update(first["id"], {"version": 1, "items": [
            {"description": "PM edited", "quantity": 20, "unitPrice": "25.00"}]})
        second = self.service.create("demo")
        self.assertEqual(second["version"], 2)
        self.assertEqual(second["total"], "500.00")
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(len(self.store.list("activity")), 1)

    def test_real_http_adapter_uses_timeout_and_server_secret_header(self):
        with patch("backend.drafting.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response()).encode()
            OpenAIExtractor("fake-test-key", "test-model").extract("message", {})
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
            self.assertEqual(request.get_header("Authorization"), "Bearer fake-test-key")
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_draft_and_activity_creation_roll_back_together(self):
        original = self.store.put
        def failing_put(kind, key, value):
            if kind == "activity":
                raise RuntimeError("simulated disk failure")
            return original(kind, key, value)
        with patch.object(self.store, "put", side_effect=failing_put):
            with self.assertRaises(RuntimeError):
                self.service.create("demo")
        self.assertEqual(self.store.list("quotations"), [])
        self.assertNotIn("status", self.store.get("enquiries", "demo"))

    def test_message_arriving_during_ai_call_is_not_overwritten(self):
        def receive_during_call(payload):
            with self.store.transaction():
                enquiry = self.store.get("enquiries", "demo")
                enquiry["text"] += "\nAlso need 10 caps"
                self.store.put("enquiries", "demo", enquiry)
            return response()
        self.transport.side_effect = receive_during_call
        self.service.create("demo")
        self.assertIn("10 caps", self.store.get("enquiries", "demo")["text"])

    def test_dotenv_does_not_execute_or_override_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/".env"
            path.write_text('# comment\nOPENAI_API_KEY="file-value"\nPORT=8000\nLITERAL=$(whoami)\n', encoding="utf-8")
            environment = {"OPENAI_API_KEY": "process-value"}
            load_env(path, environment)
            self.assertEqual(environment["OPENAI_API_KEY"], "process-value")
            self.assertEqual(environment["PORT"], "8000")
            self.assertEqual(environment["LITERAL"], "$(whoami)")


if __name__ == "__main__":
    unittest.main()
