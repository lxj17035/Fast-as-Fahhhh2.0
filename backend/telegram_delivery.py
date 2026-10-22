"""Upload saved PDF bytes to Telegram; never return raw provider errors/tokens."""
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass(frozen=True)
class DeliveryResult:
    outcome: str
    reference: str | None = None
    error: str | None = None
    retry_after: int | None = None


class TelegramDocumentSender:
    def __init__(self, token=None, transport=None):
        self.token = token or ""
        self.transport = transport or urlopen

    @property
    def configured(self):
        return bool(re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", self.token))

    def send_document(self, chat_id, pdf, filename):
        if not self.configured:
            return DeliveryResult("failed", error="Telegram bot token is not configured")
        boundary = "QuoteFlow" + uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\n'
            'Content-Type: application/pdf\r\n\r\n'
        ).encode("utf-8") + pdf + f'\r\n--{boundary}--\r\n'.encode("ascii")
        request = Request("https://api.telegram.org/bot" + self.token + "/sendDocument", data=body,
                          headers={"Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
        try:
            with self.transport(request, timeout=30) as response:
                status = response.status
                payload = response.read(1_000_001)
        except HTTPError as error:
            status = error.code
            try:
                payload = error.read(1_000_001)
            except Exception:
                return DeliveryResult("uncertain", error="Telegram outcome is unknown; check the original chat")
            finally:
                error.close()
        except (URLError, TimeoutError, OSError):
            return DeliveryResult("uncertain", error="Telegram outcome is unknown; check the original chat")
        try:
            if len(payload) > 1_000_000:
                raise ValueError()
            result = json.loads(payload)
            if status >= 500 or not isinstance(result, dict):
                raise ValueError()
            if result.get("ok") is False:
                code = result.get("error_code")
                code = code if type(code) is int and 400 <= code < 500 else None
                wait = (result.get("parameters") or {}).get("retry_after")
                wait = wait if type(wait) is int and wait > 0 else None
                return DeliveryResult("failed", error="Telegram rejected the document" +
                                      (f" (error {code})" if code else ""), retry_after=wait)
            message = result["result"]
            if (status != 200 or result.get("ok") is not True or
                    type(message["message_id"]) is not int or message["message_id"] <= 0 or
                    str(message["chat"]["id"]) != str(chat_id) or not message["document"]["file_id"]):
                raise ValueError()
            return DeliveryResult("accepted", reference=str(message["message_id"]))
        except (ValueError, TypeError, KeyError, AttributeError):
            return DeliveryResult("uncertain", error="Telegram outcome is unknown; check the original chat")
