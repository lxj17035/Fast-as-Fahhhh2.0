"""Exercise Xinjie's real services and PDF renderer; only Telegram is replaced."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.database import send_attempts
from app.main import create_app
from backend.drafting import ProviderError
from app.telegram_client import DeliveryResult


class RecordingTelegram:
    def __init__(self):
        self.calls = []
        self.result = DeliveryResult("sent", message_id="87654321")
        self.entered = None
        self.release = None

    def send_pdf(self, chat_id, pdf):
        self.calls.append((chat_id, pdf))
        if self.entered is not None:
            self.entered.set()
            if not self.release.wait(timeout=15):
                raise TimeoutError("Test did not release sender")
        return self.result


@pytest.fixture
def integrated(engine, settings, headers, update, monkeypatch):
    def forbid_ai(*args, **kwargs):
        raise ProviderError("Synthetic unavailable AI; review manually")

    monkeypatch.setattr("backend.drafting.OpenAIExtractor.extract", forbid_ai)
    sender = RecordingTelegram()
    app = create_app(replace(settings, enable_demo_approval=True), engine,
                     telegram_sender=sender)
    with TestClient(app) as client:
        response = client.post("/api/webhooks/telegram", headers=headers, json=update)
        assert response.status_code == 200
        enquiry = client.get("/api/enquiries").json()["items"][0]
        yield client, sender, enquiry


def draft(client, enquiry):
    response = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True})
    assert response.status_code == 200, response.text
    quotation = response.json()
    assert quotation["draftMode"] == "manual"
    return quotation


def edit(client, quotation, /, **fields):
    return client.patch(f"/api/quotations/{quotation['id']}",
                        json={"version": quotation["version"], **fields})


def ready(client, enquiry):
    quotation = draft(client, enquiry)
    response = edit(client, quotation, client={"name": "Fictional Customer"}, items=[{
        "description": "Fictional printed shirts", "quantity": "20", "unitPrice": "25.00"
    }], missingInformation=[])
    assert response.status_code == 200, response.text
    return response.json()


def preview(client, quotation):
    return client.get(f"/api/quotations/{quotation['id']}/pdf",
                      params={"version": quotation["version"]})


def deliver(client, quotation):
    return client.post(f"/api/quotations/{quotation['id']}/send",
                       headers={"X-Demo-Actor": "pm"},
                       json={"expected_version": quotation["version"], "approved": True})


def test_real_manual_draft_pdf_and_delivery_round_trip(integrated, engine, update):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert quotation["version"] == 2
    assert quotation["total"] == "500.00"
    response = preview(client, quotation)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["X-Quotation-Version"] == "2"
    pdf = response.content
    reader = PdfReader(BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Fictional printed shirts" in text
    assert "500.00" in text
    assert preview(client, quotation).content == pdf
    result = deliver(client, quotation)
    assert result.status_code == 200, result.text
    assert sender.calls == [(update["message"]["chat"]["id"], pdf)]
    saved = client.get(f"/api/quotations/{quotation['id']}").json()
    assert saved["status"] == "sent"
    assert saved["providerReference"] == "87654321"
    assert saved["version"] == 2
    with engine.connect() as connection:
        [attempt] = connection.execute(select(send_attempts)).mappings().all()
    assert attempt["status"] == "sent"
    assert attempt["pdf_bytes"] == pdf
    assert attempt["provider_message_id"] == "87654321"
    assert deliver(client, quotation).status_code == 409
    assert len(sender.calls) == 1


def test_send_requires_current_saved_preview(integrated):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert deliver(client, quotation).status_code == 409
    assert preview(client, quotation).status_code == 200
    updated = edit(client, quotation, notes="PM updated the terms").json()
    assert updated["version"] == 3
    assert deliver(client, quotation).status_code == 409
    assert deliver(client, updated).status_code == 409
    assert sender.calls == []
    assert preview(client, updated).status_code == 200
    assert deliver(client, updated).status_code == 200


@pytest.mark.parametrize("patch", [
    {"missingInformation": ["Confirm fictional delivery date"]},
    {"items": [{"description": "Unpriced shirt", "quantity": "1", "unitPrice": None}]},
    {"client": {"name": "", "address": ""}},
])
def test_real_saved_validation_blocks_incomplete_quotation(integrated, patch):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    response = edit(client, quotation, **patch)
    assert response.status_code == 200, response.text
    invalid = response.json()
    preview(client, invalid)
    assert deliver(client, invalid).status_code in {400, 422}
    assert sender.calls == []


def test_settings_and_client_changes_cannot_change_sent_pdf(integrated):
    client, _, enquiry = integrated
    quotation = ready(client, enquiry)
    pdf = preview(client, quotation).content
    assert deliver(client, quotation).status_code == 200
    assert client.patch("/api/settings", json={"companyName": "Changed fictional company"}).status_code == 200
    assert client.patch("/api/clients/demo-client", json={"name": "Changed fictional client"}).status_code == 200
    saved = client.get(f"/api/quotations/{quotation['id']}").json()
    assert saved["company"] == quotation["company"]
    assert saved["client"] == quotation["client"]
    assert preview(client, quotation).content == pdf
    assert edit(client, quotation, notes="Late edit").status_code == 409


@pytest.mark.parametrize("field,value", [("quantity", "0"), ("unitPrice", "-1.00")])
def test_real_item_validation_rejects_invalid_values(integrated, field, value):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    item = {"description": "Fictional shirts", "quantity": "2", "unitPrice": "10.00", field: value}
    assert edit(client, quotation, items=[item]).status_code in {400, 422}
    saved = client.get(f"/api/quotations/{quotation['id']}").json()
    assert saved["version"] == quotation["version"]
    assert saved["items"] == quotation["items"]
    assert sender.calls == []


def test_real_expiry_validation_blocks_sending(integrated):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    response = edit(client, quotation, issueDate="2000-01-01", validity="7d")
    assert response.status_code == 200
    expired = response.json()
    preview(client, expired)
    assert deliver(client, expired).status_code in {400, 422}
    assert sender.calls == []


@pytest.mark.parametrize("outcome,quotation_status", [("sent", "sent"), ("unknown", "send_uncertain")])
def test_pending_and_final_quotation_are_locked(integrated, outcome, quotation_status):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert preview(client, quotation).status_code == 200
    sender.result = DeliveryResult(outcome, message_id="87654321" if outcome == "sent" else None)
    sender.entered, sender.release = Event(), Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(deliver, client, quotation)
        try:
            assert sender.entered.wait(timeout=10)
            assert edit(client, quotation, notes="Concurrent edit").status_code == 409
            assert client.get(f"/api/quotations/{quotation['id']}").json()["status"] == "sending"
        finally:
            sender.release.set()
        response = pending.result(timeout=10)
    assert response.status_code == (200 if outcome == "sent" else 202)
    assert client.get(f"/api/quotations/{quotation['id']}").json()["status"] == quotation_status
    assert edit(client, quotation, notes="Another edit").status_code == 409
    assert deliver(client, quotation).status_code == 409
    assert len(sender.calls) == 1


def test_simultaneous_real_drafts_share_one_quotation(integrated):
    client, _, enquiry = integrated
    barrier = Barrier(4)

    def create(_):
        barrier.wait(timeout=10)
        return draft(client, enquiry)

    with ThreadPoolExecutor(max_workers=4) as pool:
        quotations = list(pool.map(create, range(4)))
    assert len({quotation["id"] for quotation in quotations}) == 1
    assert all(quotation["version"] == 1 for quotation in quotations)


def test_concurrent_edit_and_send_cannot_send_unreviewed_version(integrated):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    original_pdf = preview(client, quotation).content
    barrier = Barrier(2)

    def race_send():
        barrier.wait(timeout=10)
        return deliver(client, quotation)

    def race_edit():
        barrier.wait(timeout=10)
        return edit(client, quotation, notes="New terms need a new preview")

    with ThreadPoolExecutor(max_workers=2) as pool:
        sent = pool.submit(race_send)
        edited = pool.submit(race_edit)
        send_response = sent.result(timeout=15)
        edit_response = edited.result(timeout=15)
    assert sorted([send_response.status_code, edit_response.status_code]) == [200, 409]
    saved = client.get(f"/api/quotations/{quotation['id']}").json()
    if send_response.status_code == 200:
        assert saved["status"] == "sent"
        assert saved["version"] == 2
        assert len(sender.calls) == 1
        assert sender.calls[0][1] == original_pdf
    else:
        assert saved["version"] == 3
        assert saved["status"] == "draft"
        assert sender.calls == []


def test_failed_finalization_keeps_real_quotation_reserved(integrated, engine):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert preview(client, quotation).status_code == 200

    def fail_outcome(connection, cursor, statement, parameters, context, executemany):
        if statement.upper().startswith("UPDATE SEND_ATTEMPTS"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic outcome failure"))

    event.listen(engine, "before_cursor_execute", fail_outcome)
    try:
        response = deliver(client, quotation)
    finally:
        event.remove(engine, "before_cursor_execute", fail_outcome)
    assert response.status_code == 503
    assert response.json()["status"] == "unknown"
    assert client.get(f"/api/quotations/{quotation['id']}").json()["status"] == "sending"
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    assert detail["status"] == "unknown"
    assert detail["delivery_attempts"][0]["status"] == "pending"
    assert edit(client, quotation, notes="Unsafe edit").status_code == 409
    assert deliver(client, quotation).status_code == 409
    assert len(sender.calls) == 1
