"""Isolated compatibility service checks; public API coverage is test_delivery.py."""
from unittest.mock import Mock
import pytest
from backend.server import Application
from backend.errors import AppError
from backend.store import Store
from backend.drafting import OpenAIExtractor
from backend.telegram_delivery import DeliveryResult

@pytest.fixture
def ready_quote(tmp_path):
    store = Store.for_test(tmp_path / "compat.sqlite")
    app = Application(store, OpenAIExtractor("", ""))
    _, enquiry = app.route("POST", "/api/demo/enquiries", {"text": "Fictional shirts"}, {})
    with store.transaction():
        store.put("enquiries", enquiry["id"], {**enquiry, "source": "telegram", "chatId": "12345"})
    quote = app.drafts.create(enquiry["id"], manual=True)
    quote = app.quotations.update(quote["id"], {"version": 1, "missingInformation": [],
        "items": [{"description": "Shirts", "quantity": 20, "unitPrice": "25.00"}]}, role="pm")
    app.pdfs.get(quote["id"], 2)
    sender = Mock(configured=True)
    sender.send_document.return_value = DeliveryResult("accepted", reference="9001")
    app.sending.sender = sender
    yield app, quote, {"version": 2, "previewedVersion": 2, "actor": "Fictional PM", "role": "pm", "approved": True}, sender
    store.close()

def test_compat_acceptance_is_idempotent_and_logged(ready_quote):
    app, quote, body, sender = ready_quote
    assert app.sending.send(quote["id"], body)[0] == 200
    assert app.sending.send(quote["id"], body)[0] == 200
    assert sender.send_document.call_count == 1
    assert [e["action"] for e in app.store.list("activity")] == ["draft_created", "quotation_approved", "telegram_accepted"]

def test_compat_known_failure_requires_explicit_retry(ready_quote):
    app, quote, body, sender = ready_quote
    sender.send_document.side_effect = [DeliveryResult("failed", error="Rejected"), DeliveryResult("accepted", reference="9002")]
    assert app.sending.send(quote["id"], body)[0] == 502
    with pytest.raises(AppError) as error:
        app.sending.send(quote["id"], body)
    assert error.value.status == 409
    assert app.sending.send(quote["id"], {**body, "retry": True})[0] == 200
    assert sender.send_document.call_count == 2

def test_compat_unknown_outcome_blocks_retry(ready_quote):
    app, quote, body, sender = ready_quote
    sender.send_document.side_effect = TimeoutError("Private detail")
    assert app.sending.send(quote["id"], body)[0] == 202
    with pytest.raises(AppError) as error:
        app.sending.send(quote["id"], {**body, "retry": True})
    assert error.value.status == 409
    assert sender.send_document.call_count == 1
