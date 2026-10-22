import logging

import httpx
import pytest

from app.telegram_client import TelegramSender


def test_sends_one_multipart_pdf_to_stored_chat_without_logging_token(caplog):
    calls = []
    token = "synthetic-token-do-not-log"
    pdf = b"%PDF-1.7\nsynthetic document"

    def respond(request):
        calls.append(request)
        body = request.read()
        assert request.method == "POST"
        assert request.url.host == "api.telegram.org"
        assert request.url.path.endswith("/sendDocument")
        assert b'name="chat_id"\r\n\r\n-100123' in body
        assert b'filename="quotation.pdf"' in body
        assert b"application/pdf" in body and pdf in body
        assert request.extensions["timeout"]["read"] == 30
        return httpx.Response(200, json={
            "ok": True, "result": {"message_id": 42, "chat": {"id": -100123}}
        })

    caplog.set_level(logging.DEBUG)
    sender = TelegramSender(token, httpx.MockTransport(respond))
    result = sender.send_pdf(-100123, pdf)
    assert result.status == "sent" and result.message_id == "42"
    assert len(calls) == 1
    assert token not in caplog.text
    assert token not in repr(sender)


@pytest.mark.parametrize("error", [
    httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout,
    httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError,
])
def test_transport_errors_are_unknown_without_retry(error):
    calls = []

    def respond(request):
        calls.append(request)
        raise error("secret-provider-error")

    result = TelegramSender("synthetic", httpx.MockTransport(respond)).send_pdf(
        123, b"%PDF-1.7"
    )
    assert result.status == "unknown"
    assert len(calls) == 1
    assert "secret-provider-error" not in repr(result)


@pytest.mark.parametrize("code", [400, 403, 429])
def test_explicit_rejection_is_failed_without_description(code):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(code, json={
            "ok": False, "error_code": code, "description": "private detail"
        })

    result = TelegramSender("synthetic", httpx.MockTransport(respond)).send_pdf(
        123, b"%PDF-1.7"
    )
    assert result.status == "failed" and result.error_code == f"telegram_{code}"
    assert "private detail" not in repr(result)
    assert len(calls) == 1


@pytest.mark.parametrize("status,payload", [
    (500, {"ok": False, "error_code": 500}),
    (200, {"ok": True, "result": {"message_id": 42, "chat": {"id": 999}}}),
    (200, {"ok": True, "result": {"message_id": True, "chat": {"id": 123}}}),
    (200, {"ok": True}),
    (200, []),
    (200, {"ok": "true"}),
    (302, {"ok": True}),
])
def test_unconfirmed_response_is_unknown(status, payload):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, json=payload,
                              headers={"Location": "https://example.invalid"})

    result = TelegramSender("synthetic", httpx.MockTransport(respond)).send_pdf(
        123, b"%PDF-1.7"
    )
    assert result.status == "unknown"
    assert len(calls) == 1


@pytest.mark.parametrize("body", [b"not-json", b" " * (64 * 1024 + 1)],
                         ids=["malformed", "oversized"])
def test_malformed_or_oversized_response_is_unknown(body):
    sender = TelegramSender("synthetic", httpx.MockTransport(
        lambda request: httpx.Response(200, content=body)
    ))
    assert sender.send_pdf(123, b"%PDF-1.7").status == "unknown"
