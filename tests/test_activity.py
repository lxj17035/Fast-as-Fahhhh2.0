import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.activity import record_activity
from backend.telegram_delivery import DeliveryResult
from tests.test_sending import ready_quote, send


def events(client, quote):
    response = client.get(f'/api/enquiries/{quote["enquiryId"]}/activity')
    assert response.status_code == 200
    return response.json()["items"]


def test_receipt_draft_approval_and_provider_acceptance_are_visible(client, ready_quote):
    app, quote, body, sender = ready_quote
    assert send(client, quote, body).status_code == 200
    log = events(client, quote)
    assert [event["action"] for event in log] == [
        "enquiry_received", "draft_created", "quotation_approved", "telegram_accepted"]
    approved = log[2]
    assert approved["actor"] == "Fictional PM"
    assert approved["role"] == "pm"
    assert approved["version"] == 2
    assert approved["timestamp"]
    assert log[3]["attemptId"] == approved["attemptId"]
    assert log[3]["providerReference"] == "9001"
    assert log[3]["readConfirmed"] is False
    assert client.get(f'/api/quotations/{quote["id"]}/activity').json()["items"] == log


def test_duplicate_webhook_and_click_do_not_duplicate_activity(client, ready_quote, headers, update):
    app, quote, body, sender = ready_quote
    send(client, quote, body)
    first = events(client, quote)
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    assert send(client, quote, body).status_code == 200
    assert events(client, quote) == first
    assert sender.send_document.call_count == 1


@pytest.mark.parametrize("outcome,action", [("failed", "telegram_rejected"), ("uncertain", "telegram_uncertain")])
def test_failure_and_uncertainty_have_explicit_activity(client, ready_quote, outcome, action):
    app, quote, body, sender = ready_quote
    sender.send_document.return_value = DeliveryResult(outcome, error="Sanitized test outcome")
    send(client, quote, body)
    event = events(client, quote)[-1]
    assert event["action"] == action
    assert event["outcome"] == outcome
    assert event["error"] == "Sanitized test outcome"


def test_failed_approval_log_rolls_back_before_upload(client, ready_quote, monkeypatch):
    app, quote, body, sender = ready_quote
    original = app.store.put
    def failing_put(kind, key, value):
        if kind == "activity" and value["action"] == "quotation_approved":
            raise SQLAlchemyError("private raw database details")
        return original(kind, key, value)
    monkeypatch.setattr(app.store, "put", failing_put)
    response = send(client, quote, body)
    assert response.status_code == 503
    assert "private" not in response.text
    sender.send_document.assert_not_called()
    assert app.quotations.get(quote["id"])["status"] == "draft"
    assert app.store.list("send_attempts") == []
    assert len(events(client, quote)) == 2


def test_result_log_failure_keeps_pending_attempt_and_blocks_another_upload(client, ready_quote, monkeypatch):
    app, quote, body, sender = ready_quote
    original = app.store.put
    def failing_put(kind, key, value):
        if kind == "activity" and value["action"] == "telegram_accepted":
            raise SQLAlchemyError("private raw database details")
        return original(kind, key, value)
    monkeypatch.setattr(app.store, "put", failing_put)
    assert send(client, quote, body).status_code == 503
    assert app.quotations.get(quote["id"])["status"] == "sending"
    assert send(client, quote, body).status_code == 202
    assert sender.send_document.call_count == 1
    assert events(client, quote)[-1]["action"] == "quotation_approved"


def test_activity_entries_are_not_overwritten_on_repeat(client, ready_quote):
    app, quote, _, _ = ready_quote
    first = record_activity(app.store, "test-immutable", enquiryId=quote["enquiryId"], actor="system", action="test", outcome="original")
    repeated = record_activity(app.store, "test-immutable", enquiryId=quote["enquiryId"], actor="other", action="test", outcome="replacement")
    assert repeated == first


def test_missing_activity_parent_returns_404(client):
    assert client.get("/api/enquiries/missing/activity").status_code == 404
    assert client.get("/api/quotations/missing/activity").status_code == 404
