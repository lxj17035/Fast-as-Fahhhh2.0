from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from backend.server import Application
from backend.store import Store
from backend.telegram_delivery import DeliveryResult, TelegramDocumentSender


@pytest.fixture
def ready_quote(client, headers, update):
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    app = client.app.state.quotation_app
    quote, = app.store.list("quotations")
    quote = app.quotations.update(quote["id"], {"version": 1,
        "client": {"name": "Fictional Buyer"}, "missingInformation": [],
        "items": [{"description": "Printed shirts", "quantity": 20, "unitPrice": "25.00"}]})
    app.pdfs.get(quote["id"], 2)
    sender = Mock()
    sender.configured = True
    sender.send_document.return_value = DeliveryResult("accepted", reference="9001")
    app.sending.sender = sender
    body = {"version": 2, "previewedVersion": 2, "actor": "Fictional PM", "role": "pm", "approved": True}
    return app, quote, body, sender


def send(client, quote, body):
    return client.post(f'/api/quotations/{quote["id"]}/send', json=body)


def test_pm_approval_sends_exact_saved_pdf_to_original_chat(client, ready_quote, update):
    app, quote, body, sender = ready_quote
    pdf = app.pdfs.get(quote["id"], 2)[0]
    response = send(client, quote, body)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["providerReference"] == "9001"
    assert response.json()["readConfirmed"] is False
    sender.send_document.assert_called_once_with(str(update["message"]["chat"]["id"]), pdf, quote["number"] + ".pdf")
    assert app.store.get("enquiries", quote["enquiryId"])["status"] == "sent"
    assert app.quotations.get(quote["id"])["approvedBy"] == "Fictional PM"
    assert client.get(f'/api/enquiries/{quote["enquiryId"]}/quotation').json()["id"] == quote["id"]


@pytest.mark.parametrize("patch,status", [({"role": "sales"}, 403), ({"approved": False}, 422),
    ({"approved": "true"}, 422), ({"actor": ""}, 422), ({"version": True}, 422),
    ({"previewedVersion": 1}, 409), ({"chatId": "123"}, 422)])
def test_invalid_approval_or_recipient_override_never_sends(client, ready_quote, patch, status):
    app, quote, body, sender = ready_quote
    assert send(client, quote, {**body, **patch}).status_code == status
    sender.send_document.assert_not_called()
    assert app.quotations.get(quote["id"])["status"] == "draft"


def test_missing_token_does_not_consume_approval(client, ready_quote):
    app, quote, body, _ = ready_quote
    app.sending.sender = TelegramDocumentSender()
    assert send(client, quote, body).status_code == 503
    assert app.quotations.get(quote["id"])["status"] == "draft"
    assert app.store.list("send_attempts") == []


def test_saved_pdf_must_be_previewed_after_edit(client, ready_quote):
    app, quote, body, sender = ready_quote
    app.quotations.update(quote["id"], {"version": 2, "notes": "New terms for PM review"})
    assert send(client, quote, body).status_code == 409
    body.update(version=3, previewedVersion=3)
    assert send(client, quote, body).status_code == 409
    app.pdfs.get(quote["id"], 3)
    assert send(client, quote, body).status_code == 200
    assert sender.send_document.call_count == 1


def test_blank_prices_block_send(client, ready_quote):
    app, quote, body, sender = ready_quote
    app.quotations.update(quote["id"], {"version": 2, "items": [
        {"description": "Unknown pricing", "quantity": 1, "unitPrice": None}]})
    body.update(version=3, previewedVersion=3)
    app.pdfs.get(quote["id"], 3)
    response = send(client, quote, body)
    assert response.status_code == 422
    assert "items.0.unitPrice" in response.json()["fields"]
    sender.send_document.assert_not_called()


def test_repeat_click_after_acceptance_does_not_send_again(client, ready_quote):
    app, quote, body, sender = ready_quote
    first = send(client, quote, body)
    second = send(client, quote, body)
    assert second.status_code == 200
    assert first.json()["attemptId"] == second.json()["attemptId"]
    assert sender.send_document.call_count == 1
    assert len(app.store.list("send_attempts")) == 1


def test_pending_concurrent_click_returns_same_attempt(client, ready_quote):
    app, quote, body, sender = ready_quote
    started, release = Event(), Event()
    def block(*args):
        started.set()
        assert release.wait(5)
        return DeliveryResult("accepted", reference="9001")
    sender.send_document.side_effect = block
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send, client, quote, body)
        assert started.wait(5)
        try:
            duplicate = send(client, quote, body)
            assert duplicate.status_code == 202
            assert duplicate.json()["status"] == "sending"
        finally:
            release.set()
        assert first.result().status_code == 200
    assert sender.send_document.call_count == 1


def test_known_failure_needs_explicit_retry_approval(client, ready_quote):
    app, quote, body, sender = ready_quote
    sender.send_document.side_effect = [DeliveryResult("failed", error="Telegram rejected the document"),
                                        DeliveryResult("accepted", reference="9002")]
    assert send(client, quote, body).status_code == 502
    assert app.store.get("enquiries", quote["enquiryId"])["status"] == "failed"
    assert send(client, quote, body).status_code == 409
    assert send(client, quote, {**body, "retry": True}).status_code == 200
    assert sender.send_document.call_count == 2
    assert len(app.store.list("send_attempts")) == 2


def test_uncertain_result_blocks_blind_resend(client, ready_quote):
    app, quote, body, sender = ready_quote
    sender.send_document.side_effect = TimeoutError("private provider detail")
    response = send(client, quote, body)
    assert response.status_code == 202
    assert response.json()["status"] == "send_uncertain"
    assert "private" not in response.text
    assert app.store.get("enquiries", quote["enquiryId"])["status"] == "unknown"
    assert send(client, quote, {**body, "retry": True}).status_code == 409
    assert sender.send_document.call_count == 1


def test_accepted_attempt_survives_reopening_store(client, ready_quote, engine):
    app, quote, body, sender = ready_quote
    send(client, quote, body)
    reopened = Application(Store(engine=engine))
    reopened.sending.sender = Mock(configured=True)
    status, response = reopened.sending.send(quote["id"], body)
    assert status == 200
    assert response["status"] == "sent"
    reopened.sending.sender.send_document.assert_not_called()
