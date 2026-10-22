import json
from io import BytesIO
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError

import pytest

from backend.telegram_delivery import TelegramDocumentSender


def transport_response(payload, status=200):
    transport = MagicMock()
    response = transport.return_value.__enter__.return_value
    response.status = status
    response.read.return_value = json.dumps(payload).encode()
    return transport


def accepted(chat_id=-100123):
    return {"ok": True, "result": {"message_id": 9001, "chat": {"id": chat_id},
                                   "document": {"file_id": "fictional-file-id"}}}


def test_adapter_uploads_pdf_bytes_as_multipart_and_returns_reference():
    transport = transport_response(accepted())
    sender = TelegramDocumentSender("123:fake-test-token", transport)
    result = sender.send_document("-100123", b"%PDF-synthetic-bytes", "QUO-DEMO.pdf")
    assert result.outcome == "accepted"
    assert result.reference == "9001"
    request = transport.call_args.args[0]
    assert request.full_url == "https://api.telegram.org/bot123:fake-test-token/sendDocument"
    assert b'%PDF-synthetic-bytes' in request.data
    assert b'name="chat_id"\r\n\r\n-100123' in request.data
    assert 'multipart/form-data' in request.get_header('Content-type')
    assert transport.call_args.kwargs["timeout"] == 30


def test_telegram_rejection_never_echoes_raw_description():
    transport = transport_response({"ok": False, "error_code": 403, "description": "private token or customer text"}, 403)
    result = TelegramDocumentSender("123:fake", transport).send_document("-100123", b"pdf", "QUO.pdf")
    assert result.outcome == "failed"
    assert "private" not in result.error
    assert "403" in result.error


def test_http_error_is_sanitized_and_retry_after_is_exposed():
    transport = Mock(side_effect=HTTPError("https://private-token", 429, "private detail", None, BytesIO(
        json.dumps({"ok": False, "error_code": 429, "parameters": {"retry_after": 30}}).encode())))
    result = TelegramDocumentSender("123:fake", transport).send_document("-100123", b"pdf", "QUO.pdf")
    assert result.outcome == "failed"
    assert result.retry_after == 30
    assert "private" not in result.error


@pytest.mark.parametrize("payload,status", [(accepted(999), 200), ({"ok": True, "result": {}}, 200),
    (accepted(), 500), ({"ok": False}, 503), ([], 200)])
def test_ambiguous_response_is_uncertain(payload, status):
    result = TelegramDocumentSender("123:fake", transport_response(payload, status)).send_document("-100123", b"pdf", "QUO.pdf")
    assert result.outcome == "uncertain"


def test_timeout_is_not_treated_as_safe_to_retry():
    transport = Mock(side_effect=TimeoutError("private token"))
    result = TelegramDocumentSender("123:fake", transport).send_document("-100123", b"pdf", "QUO.pdf")
    assert result.outcome == "uncertain"
    assert "private" not in result.error


def test_unconfigured_sender_does_not_call_transport():
    transport = Mock()
    result = TelegramDocumentSender("", transport).send_document("-100123", b"pdf", "QUO.pdf")
    assert result.outcome == "failed"
    transport.assert_not_called()
