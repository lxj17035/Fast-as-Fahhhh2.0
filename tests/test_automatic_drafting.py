from unittest.mock import Mock

from sqlalchemy import select

from app.database import enquiries
from backend.drafting import ProviderError


def enquiry_id(engine, update):
    with engine.connect() as connection:
        return connection.execute(select(enquiries.c.id).where(
            enquiries.c.telegram_update_id == update["update_id"])).scalar_one()


def test_receipt_automatically_creates_draft_without_an_extra_request(client, engine, headers, update):
    app = client.app.state.quotation_app
    app.drafts.extractor = Mock()
    app.drafts.extractor.extract.return_value = {
        "summary": "Fictional event shirts", "clientName": "Fictional Customer", "clientAddress": None,
        "items": [{"description": "Printed shirts", "quantity": 20, "unitPrice": None}],
        "missingInformation": [],
    }
    response = client.post("/api/webhooks/telegram", headers=headers, json=update)
    assert response.status_code == 200
    quote, = app.store.list("quotations")
    assert quote["enquiryId"] == enquiry_id(engine, update)
    assert quote["draftMode"] == "ai"
    assert quote["items"][0]["unitPrice"] is None
    assert quote["status"] == "draft"
    app.drafts.extractor.extract.assert_called_once()


def test_duplicate_update_preserves_existing_pm_edits(client, headers, update):
    app = client.app.state.quotation_app
    app.drafts.extractor = Mock()
    app.drafts.extractor.extract.side_effect = ProviderError("AI unavailable; review manually")
    client.post("/api/webhooks/telegram", headers=headers, json=update)
    quote, = app.store.list("quotations")
    app.quotations.update(quote["id"], {"version": 1, "notes": "PM working draft"})
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).json()["status"] == "duplicate"
    assert app.quotations.get(quote["id"])["notes"] == "PM working draft"
    assert app.drafts.extractor.extract.call_count == 1


def test_ai_failure_automatically_creates_labelled_manual_draft(client, headers, update):
    app = client.app.state.quotation_app
    app.drafts.extractor = Mock()
    app.drafts.extractor.extract.side_effect = ProviderError("AI unavailable; review manually")
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    quote, = app.store.list("quotations")
    assert quote["draftMode"] == "manual"
    assert quote["draftError"] == "AI unavailable; review manually"


def test_unexpected_draft_failure_keeps_receipt_and_duplicate_can_retry(client, engine, headers, update, monkeypatch):
    app = client.app.state.quotation_app
    original = app.drafts.create
    monkeypatch.setattr(app.drafts, "create", Mock(side_effect=RuntimeError("private raw detail")))
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    assert enquiry_id(engine, update)
    assert app.store.list("quotations") == []
    monkeypatch.setattr(app.drafts, "create", original)
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    assert len(app.store.list("quotations")) == 1
