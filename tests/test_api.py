import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.drafting import OpenAIExtractor
from backend.server import Application, LocalServer, handler_for
from backend.store import Store


class APITests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.app = Application(self.store, OpenAIExtractor("", ""))
        self.server = LocalServer(("127.0.0.1", 0), handler_for(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.store.close()

    def request(self, method, route, body=None, *, raw=None, headers=None):
        payload = json.dumps(body).encode() if body is not None else raw
        request = Request(self.base + route, data=payload, method=method,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            content = data if response.headers.get_content_type() == "application/pdf" else json.loads(data)
            return response.status, content, response.headers

    def draft(self):
        status, enquiry, _ = self.request("POST", "/api/demo/enquiries", {"text": "Need 20 fictional event shirts"})
        self.assertEqual(status, 201)
        self.assertEqual(enquiry["source"], "demo")
        status, quote, _ = self.request("POST", f'/api/enquiries/{enquiry["id"]}/draft', {"manual": True})
        self.assertEqual(status, 200)
        return enquiry, quote

    def test_settings_and_client_edit_routes(self):
        self.assertEqual(self.request("GET", "/api/health")[0], 200)
        self.assertEqual(self.request("GET", "/api/settings")[1]["defaultValidity"], "1m")
        self.assertEqual(self.request("PATCH", "/api/settings", {"defaultValidity": "14d"})[0], 200)
        self.assertEqual(self.request("PATCH", "/api/clients/demo-client", {"name": "Demo New"})[0], 200)
        self.assertEqual(self.request("GET", "/api/clients/demo-client")[1]["name"], "Demo New")

    def test_demo_to_priced_pdf_round_trip(self):
        enquiry, quote = self.draft()
        status, saved, _ = self.request("PATCH", f'/api/quotations/{quote["id"]}', {
            "version": 1, "missingInformation": [], "items": [
                {"description": "Fictional printed shirts", "quantity": 20, "unitPrice": "25.00"}]})
        self.assertEqual(status, 200)
        self.assertEqual(saved["total"], "500.00")
        status, pdf, headers = self.request("GET", f'/api/quotations/{quote["id"]}/pdf?version=2')
        self.assertEqual(status, 200)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertEqual(headers["X-Quotation-Version"], "2")
        detail = self.request("GET", f'/api/enquiries/{enquiry["id"]}')[1]
        self.assertEqual(detail["context"]["source"], "synthetic-seed")
        self.assertEqual(len(detail["activity"]), 1)
        self.assertEqual(len(self.request("GET", "/api/enquiries")[1]), 1)

    def test_stale_save_and_pdf_are_conflicts(self):
        _, quote = self.draft()
        path = f'/api/quotations/{quote["id"]}'
        self.request("PATCH", path, {"version": 1, "notes": "Edited"})
        self.assertEqual(self.request("PATCH", path, {"version": 1, "notes": "Stale"})[0], 409)
        self.assertEqual(self.request("GET", path + "/pdf?version=1")[0], 409)
        self.assertEqual(self.request("GET", path + "/pdf?version=bad")[0], 422)

    def test_missing_route_client_and_quote_return_404(self):
        for route in ["/api/nope", "/api/clients/missing", "/api/quotations/missing", "/api/enquiries/missing"]:
            self.assertEqual(self.request("GET", route)[0], 404)

    def test_invalid_json_nonfinite_values_and_nonobject_body(self):
        for body in [b"{broken", b'{"currency":NaN}', b"[]", b"null"]:
            self.assertEqual(self.request("PATCH", "/api/settings", raw=body)[0], 400)

    def test_field_validation_and_content_type(self):
        self.assertEqual(self.request("PATCH", "/api/settings", {"currency": "bad"})[0], 422)
        self.assertEqual(self.request("POST", "/api/demo/enquiries", {"text": ""})[0], 422)
        self.assertEqual(self.request("PATCH", "/api/settings", {}, headers={"Content-Type": "text/plain"})[0], 415)

    def test_local_cors_and_untrusted_origin_rejection(self):
        status, _, headers = self.request("GET", "/api/settings", headers={"Origin": "http://localhost:3000"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")
        self.assertEqual(self.request("PATCH", "/api/settings", {"currency": "USD"},
                                     headers={"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.app.settings.get_settings()["currency"], "MYR")

    def test_send_is_explicitly_not_implemented(self):
        _, quote = self.draft()
        status, error, _ = self.request("POST", f'/api/quotations/{quote["id"]}/send', {})
        self.assertEqual(status, 501)
        self.assertIn("no message was sent", error["error"])

    def test_no_key_returns_labelled_manual_draft_and_no_secret_fields(self):
        _, quote = self.draft()
        self.assertEqual(quote["draftMode"], "manual")
        settings = self.request("GET", "/api/settings")[1]
        self.assertNotIn("OPENAI_API_KEY", settings)
