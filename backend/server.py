import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from .config import load_env
from .drafting import DraftService
from .errors import AppError, object_fields, text
from .pdf import PDFService
from .quotations import QuotationService
from .settings import SettingsService, require_profile
from .store import Store
from .sending import SendService
from .telegram_delivery import TelegramDocumentSender
from .activity import enquiry_activity

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ORIGINS = {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
                   for port in (3000, 5173, 8004)}


class Application:
    def __init__(self, store, extractor=None, telegram_token=None):
        self.store = store
        self.settings = SettingsService(store)
        self.quotations = QuotationService(store, self.settings)
        self.drafts = DraftService(store, self.settings, self.quotations, extractor)
        self.pdfs = PDFService(store, self.quotations)
        self.sending = SendService(store, self.quotations, self.pdfs, TelegramDocumentSender(telegram_token))

    def route(self, method, path, body, query):
        parts = [part for part in path.split("/") if part]
        if path == "/api/health" and method == "GET":
            return 200, {"status": "ok", "mode": "local-synthetic-demo"}
        if path == "/api/settings":
            if method == "GET":
                return 200, self.settings.get_settings()
            if method == "PATCH":
                return 200, self.settings.update_settings(body)
        if path == "/api/business-profiles" and method == "GET":
            return 200, self.settings.list_profiles()
        if path == "/api/business-profiles/active" and method == "PATCH":
            return 200, self.settings.select_profile(body)
        if len(parts) == 3 and parts[:2] == ["api", "business-profiles"]:
            if method == "GET":
                return 200, self.settings.get_profile(parts[2])
            if method == "PATCH":
                return 200, self.settings.update_settings(body, parts[2])
        if len(parts) == 3 and parts[:2] == ["api", "clients"]:
            if method == "GET":
                return 200, self.settings.get_client(parts[2])
            if method == "PATCH":
                return 200, self.settings.update_client(parts[2], body)
        if path == "/api/demo/enquiries" and method == "POST":
            object_fields(body, {"text", "clientId"})
            with self.store.transaction():
                identity = self.settings.active_profile_id()
                client_id = body.get("clientId", self.settings.demo_client_id(identity))
                self.settings.get_client(text(client_id, "clientId", required=True), identity)
                key = uuid4().hex
                enquiry = {"id": key, "text": text(body.get("text"), "text", required=True, limit=20000),
                           "business_profile_id": identity, "clientId": client_id,
                           "source": "demo", "chatId": "demo-chat", "status": "received"}
                self.store.put("enquiries", key, enquiry)
            return 201, enquiry
        if path == "/api/enquiries" and method == "GET":
            identity = self.settings.active_profile_id()
            return 200, [item for item in self.store.list("enquiries") if item["business_profile_id"] == identity]
        if len(parts) >= 3 and parts[:2] == ["api", "enquiries"]:
            enquiry = require_profile(self.store.get("enquiries", parts[2]), self.settings.active_profile_id())
            if len(parts) == 3 and method == "GET":
                return 200, {**enquiry, "context": {
                    "company": self.settings.get_settings(enquiry["business_profile_id"]),
                    "client": self.settings.get_client(enquiry["clientId"]) if enquiry.get("clientId") else None,
                    "source": "stored-business-context" if enquiry["source"] == "telegram" else "synthetic-seed"},
                    "quotations": [q for q in self.store.list("quotations") if q["enquiryId"] == parts[2]],
                    "activity": [a for a in self.store.list("activity") if a["enquiryId"] == parts[2]]}
            if len(parts) == 4 and parts[3] == "draft" and method == "POST":
                object_fields(body, {"manual"})
                if not isinstance(body.get("manual", False), bool):
                    raise AppError("manual must be a boolean")
                return 200, self.drafts.create(parts[2], manual=body.get("manual", False))
            if len(parts) == 4 and parts[3] == "quotation" and method == "GET":
                self.store.get("enquiries", parts[2])
                for quote in reversed(self.store.list("quotations")):
                    if quote["enquiryId"] == parts[2]:
                        return 200, quote
                raise AppError("Draft is not available yet; refresh or retry drafting", 404)
            if len(parts) == 4 and parts[3] == "activity" and method == "GET":
                return 200, {"items": enquiry_activity(self.store, parts[2])}
        if len(parts) >= 3 and parts[:2] == ["api", "quotations"]:
            require_profile(self.quotations.get(parts[2]), self.settings.active_profile_id())
            if len(parts) == 4 and parts[3] == "activity" and method == "GET":
                quote = self.quotations.get(parts[2])
                return 200, {"items": enquiry_activity(self.store, quote["enquiryId"])}
            if len(parts) == 3:
                if method == "GET":
                    return 200, self.quotations.get(parts[2])
                if method == "PATCH":
                    return 200, self.quotations.update(parts[2], body)
            if len(parts) == 4 and parts[3] == "pdf" and method == "GET":
                version = None
                if "version" in query:
                    try:
                        version = int(query["version"][0])
                    except ValueError:
                        raise AppError("version must be an integer") from None
                data, version = self.pdfs.get(parts[2], version)
                return 200, data, {"Content-Type": "application/pdf", "X-Quotation-Version": str(version),
                                   "Content-Disposition": f'inline; filename="quotation-{parts[2]}.pdf"'}
            if len(parts) == 4 and parts[3] == "send" and method == "POST":
                return self.sending.send(parts[2], body)
        raise AppError("Route not found", 404)


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Avoid recording enquiry bodies, keys, or raw provider errors.

        def handle_request(self):
            headers = {}
            try:
                if self.headers.get("Origin") not in (None, *ALLOWED_ORIGINS):
                    raise AppError("Origin is not allowed for this local demo", 403)
                body = {}
                if self.command in ("POST", "PATCH"):
                    if self.headers.get_content_type() != "application/json":
                        raise AppError("Use Content-Type: application/json", 415)
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        raise AppError("Invalid Content-Length", 400) from None
                    if length < 0 or length > 256000:
                        raise AppError("Request body is too large", 413)
                    try:
                        def invalid_constant(_):
                            raise ValueError("Non-finite number")
                        body = json.loads(self.rfile.read(length), parse_constant=invalid_constant)
                    except (ValueError, UnicodeError):
                        raise AppError("Body must be valid JSON", 400) from None
                    if not isinstance(body, dict):
                        raise AppError("Body must be a JSON object", 400)
                url = urlparse(self.path)
                result = app.route(self.command, url.path, body, parse_qs(url.query, keep_blank_values=True))
                status, payload = result[:2]
                if len(result) == 3:
                    headers = result[2]
            except AppError as error:
                status, payload = error.status, {"error": str(error), "fields": error.fields}
            except Exception:
                status, payload = 500, {"error": "Internal error; no successful action is implied", "fields": {}}
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", headers.pop("Content-Type", "application/json; charset=utf-8"))
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            origin = self.headers.get("Origin")
            if origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PATCH = handle_request

        def do_OPTIONS(self):
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                self.send_error(403)
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(30)
        return connection, address


def main():
    load_env(ROOT / ".env")
    import uvicorn
    from app.main import create_app
    try:
        application = create_app()
    except Exception:
        raise SystemExit("Startup configuration failed. Check DATABASE_URL and TELEGRAM_WEBHOOK_SECRET in local .env; private values are not logged.") from None
    uvicorn.run(application, host="127.0.0.1", port=8004)


if __name__ == "__main__":
    main()
