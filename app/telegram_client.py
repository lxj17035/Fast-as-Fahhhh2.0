"""One-shot Telegram document delivery, with no automatic retries."""

import json
from dataclasses import dataclass
from typing import Literal

import httpx


@dataclass(frozen=True)
class DeliveryResult:
    status: Literal["sent", "failed", "unknown"]
    message_id: str | None = None
    error_code: str | None = None


class TelegramSender:
    def __init__(
        self, bot_token: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._bot_token = bot_token
        self._transport = transport

    def send_pdf(self, chat_id: int, pdf: bytes) -> DeliveryResult:
        # Call the transport directly: Client's INFO request log contains the
        # bot token in Telegram's URL. No redirects, proxy environment or retries.
        request = httpx.Request(
            "POST",
            f"https://api.telegram.org/bot{self._bot_token}/sendDocument",
            data={"chat_id": str(chat_id)},
            files={"document": ("quotation.pdf", pdf, "application/pdf")},
            extensions={
                "timeout": {"connect": 10, "read": 30, "write": 30, "pool": 10}
            },
        )
        return self._deliver(request, chat_id)

    def send_text(self, chat_id: int, content: str) -> DeliveryResult:
        request = httpx.Request(
            "POST", f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            json={"chat_id": str(chat_id), "text": content},
            extensions={"timeout": {"connect": 10, "read": 30, "write": 30, "pool": 10}},
        )
        return self._deliver(request, chat_id)

    def _deliver(self, request, chat_id):
        transport = self._transport
        owns_transport = transport is None
        if transport is None:
            transport = httpx.HTTPTransport(retries=0, trust_env=False)
        try:
            response = transport.handle_request(request)
            try:
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > 64 * 1024:
                        return DeliveryResult("unknown", error_code="invalid_response")
                    body.extend(chunk)
                payload = json.loads(body)
            finally:
                response.close()
        except httpx.TimeoutException:
            return DeliveryResult("unknown", error_code="telegram_timeout")
        except httpx.TransportError:
            return DeliveryResult("unknown", error_code="telegram_transport_error")
        except (ValueError, UnicodeError, RecursionError):
            return DeliveryResult("unknown", error_code="invalid_response")
        finally:
            if owns_transport:
                transport.close()

        if not isinstance(payload, dict):
            return DeliveryResult("unknown", error_code="invalid_response")
        if 200 <= response.status_code < 300 and payload.get("ok") is True:
            result = payload.get("result")
            if isinstance(result, dict):
                message_id = result.get("message_id")
                chat = result.get("chat")
                if (
                    type(message_id) is int and message_id > 0
                    and isinstance(chat, dict)
                    and type(chat.get("id")) is int and chat["id"] == chat_id
                ):
                    return DeliveryResult("sent", message_id=str(message_id))
            return DeliveryResult("unknown", error_code="invalid_response")
        code = payload.get("error_code")
        if (
            payload.get("ok") is False and type(code) is int
            and 400 <= code < 500 and response.status_code == code
        ):
            # Never retain the provider's description: it may contain private data.
            return DeliveryResult("failed", error_code=f"telegram_{code}")
        return DeliveryResult("unknown", error_code="unconfirmed_response")
