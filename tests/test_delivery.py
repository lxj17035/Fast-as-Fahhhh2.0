"""Delivery component tests use a synthetic transactional quotation adapter."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, event, select
from sqlalchemy.exc import OperationalError

from app.database import enquiries, send_attempts
from app.main import create_app
from app.quotation_contract import QuotationItem, SavedQuotation
from app.quotation_contract import QuotationConflict, QuotationNotFound
from app.quotation_contract import UnavailableQuotationProvider
from app.telegram_client import DeliveryResult


test_metadata = MetaData()
provider_records = Table(
    "test_quotation_provider", test_metadata,
    Column("id", String(36), primary_key=True),
    Column("status", String(20), nullable=False),
)


class FakeQuotationProvider:
    """The test adapter locks and changes its row in the supplied transaction."""

    def __init__(self, snapshot):
        self.snapshot = snapshot

    def reserve_for_send(self, connection, quotation_id, expected_version):
        record = connection.execute(
            select(provider_records).where(
                provider_records.c.id == str(quotation_id)
            ).with_for_update()
        ).mappings().one()
        connection.execute(provider_records.update().where(
            provider_records.c.id == record["id"]
        ).values(status="reserved"))
        return self.snapshot

    def record_outcome(self, connection, quotation_id, status, provider_reference=None):
        connection.execute(provider_records.update().where(
            provider_records.c.id == str(quotation_id)
        ).values(status=status))


class FakeSender:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def send_pdf(self, chat_id, pdf):
        self.calls.append((chat_id, pdf))
        if self.error:
            raise self.error
        return self.result


def records(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


def provider_status(engine):
    return records(engine, provider_records)[0]["status"]


def send(client, quotation_id, **body):
    return client.post(
        f"/api/quotations/{quotation_id}/send",
        headers={"X-Demo-Actor": "pm"},
        json={"expected_version": 1, "approved": True, **body},
    )


@pytest.fixture
def delivery(engine, settings, headers, update):
    demo_settings = replace(settings, enable_demo_approval=True)
    sender = FakeSender(DeliveryResult(status="sent", message_id="987654"))
    today = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    with TestClient(create_app(demo_settings, engine)) as reception:
        reception.post("/api/webhooks/telegram", headers=headers, json=update)
        enquiry_id = reception.get("/api/enquiries").json()["items"][0]["id"]
    snapshot = SavedQuotation(
        quotation_id=str(uuid4()), enquiry_id=enquiry_id, version=1, status="ready",
        client_name="Fictional Client", issue_date=today,
        expiry_date=today + timedelta(days=7),
        items=(QuotationItem(description="Printed shirts", quantity=Decimal("20"),
                             unit_price=Decimal("25.00")),),
        pdf_version=1, pdf_bytes=b"%PDF-1.4\nsynthetic saved document\n%%EOF",
    )
    provider = FakeQuotationProvider(snapshot)
    test_metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(provider_records.insert().values(id=snapshot.quotation_id, status="ready"))
    app = create_app(demo_settings, engine, quotation_provider=provider, telegram_sender=sender)
    with TestClient(app) as client:
        yield client, provider, sender, snapshot


def test_disabled_and_missing_adapter_do_not_send(engine, settings, delivery):
    _, provider, sender, quotation = delivery
    with TestClient(create_app(settings, engine, quotation_provider=provider, telegram_sender=sender)) as client:
        assert send(client, quotation.quotation_id).status_code == 503
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              quotation_provider=UnavailableQuotationProvider(),
                              telegram_sender=sender)) as client:
        assert send(client, quotation.quotation_id).status_code == 503
    assert sender.calls == []
    assert records(engine, send_attempts) == []


@pytest.mark.parametrize("actor,expected", [(None, 401), ("sales", 403), ("AI", 401)])
def test_only_demo_pm_may_send(delivery, engine, actor, expected):
    client, _, sender, quotation = delivery
    headers = {} if actor is None else {"X-Demo-Actor": actor}
    response = client.post(f"/api/quotations/{quotation.quotation_id}/send", headers=headers,
                           json={"expected_version": 1, "approved": True})
    assert response.status_code == expected
    assert sender.calls == []
    assert records(engine, send_attempts) == []


@pytest.mark.parametrize("body", [
    {"chat_id": 123}, {"recipient": "AI-specified-recipient"}, {"approved": False},
    {"approved": 1}, {"expected_version": "1"}, {"expected_version": 0},
])
def test_invalid_approval_and_arbitrary_recipient_rejected(delivery, body):
    client, _, sender, quotation = delivery
    assert send(client, quotation.quotation_id, **body).status_code == 422
    assert sender.calls == []


@pytest.mark.parametrize("change,expected", [
    ({"client_name": " "}, 422), ({"items": ()}, 422),
    ({"pdf_bytes": b""}, 422), ({"pdf_bytes": b"not a PDF"}, 422),
    ({"pdf_bytes": b"%PDF-" + b"x" * (10 * 1024 * 1024)}, 422),
    ({"version": 2}, 409), ({"pdf_version": 2}, 409),
    ({"status": "sent"}, 409), ({"enquiry_id": str(uuid4())}, 422),
])
def test_invalid_saved_snapshot_does_not_send(delivery, engine, change, expected):
    client, provider, sender, quotation = delivery
    provider.snapshot = quotation.model_copy(update=change)
    assert send(client, quotation.quotation_id).status_code == expected
    assert sender.calls == []
    assert records(engine, send_attempts) == []
    assert provider_status(engine) == "ready"


@pytest.mark.parametrize("field,value", [
    ("quantity", Decimal("0")), ("quantity", Decimal("-1")),
    ("quantity", Decimal("NaN")), ("unit_price", None),
    ("unit_price", Decimal("-0.01")), ("unit_price", Decimal("Infinity")),
    ("description", " "),
])
def test_invalid_item_does_not_send(delivery, field, value):
    client, provider, sender, quotation = delivery
    item = quotation.items[0].model_copy(update={field: value})
    provider.snapshot = quotation.model_copy(update={"items": (item,)})
    assert send(client, quotation.quotation_id).status_code == 422
    assert sender.calls == []


@pytest.mark.parametrize("field,delta", [("expiry_date", -1), ("issue_date", 1)])
def test_expired_or_future_quotation_rejected(delivery, field, delta):
    client, provider, sender, quotation = delivery
    today = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    provider.snapshot = quotation.model_copy(update={field: today + timedelta(days=delta)})
    assert send(client, quotation.quotation_id).status_code == 422
    assert sender.calls == []


def test_zero_explicit_price_and_expiry_today_are_valid(delivery):
    client, provider, sender, quotation = delivery
    today = datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date()
    item = quotation.items[0].model_copy(update={"unit_price": Decimal("0")})
    provider.snapshot = quotation.model_copy(update={
        "expiry_date": today, "items": (item,),
    })
    assert send(client, quotation.quotation_id).status_code == 200
    assert len(sender.calls) == 1


@pytest.mark.parametrize("error,expected", [
    (QuotationConflict, 409), (QuotationNotFound, 404),
])
def test_adapter_state_errors_do_not_send(delivery, monkeypatch, error, expected):
    client, provider, sender, quotation = delivery

    def reject(*args):
        raise error("synthetic private detail")

    monkeypatch.setattr(provider, "reserve_for_send", reject)
    response = send(client, quotation.quotation_id)
    assert response.status_code == expected
    assert "synthetic private detail" not in response.text
    assert sender.calls == []


def test_missing_bot_token_prevents_reservation(delivery, engine, settings):
    _, provider, _, quotation = delivery
    no_token = replace(settings, enable_demo_approval=True, telegram_bot_token=None)
    with TestClient(create_app(no_token, engine, quotation_provider=provider)) as client:
        assert send(client, quotation.quotation_id).status_code == 503
    assert records(engine, send_attempts) == []
    assert provider_status(engine) == "ready"


def test_success_preserves_approved_pdf_and_uses_original_chat(delivery, engine, update):
    client, _, sender, quotation = delivery
    response = send(client, quotation.quotation_id)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert sender.calls == [(update["message"]["chat"]["id"], quotation.pdf_bytes)]
    [attempt] = records(engine, send_attempts)
    assert attempt["id"] == response.json()["attempt_id"]
    assert attempt["quotation_id"] == quotation.quotation_id
    assert attempt["enquiry_id"] == quotation.enquiry_id
    assert attempt["version"] == 1
    assert attempt["pdf_sha256"] == sha256(quotation.pdf_bytes).hexdigest()
    assert attempt["pdf_bytes"] == quotation.pdf_bytes
    assert attempt["actor_id"] == "pm"
    assert attempt["role"] == "pm"
    assert attempt["approved_at"] is not None
    assert attempt["status"] == "sent"
    assert str(attempt["provider_message_id"]) == "987654"
    assert provider_status(engine) == "sent"
    assert records(engine, enquiries)[0]["status"] == "sent"
    assert send(client, quotation.quotation_id).status_code == 409
    assert send(client, quotation.quotation_id, expected_version=2).status_code == 409
    assert len(sender.calls) == 1


def test_concurrent_send_calls_provider_once(delivery, engine):
    client, _, sender, quotation = delivery
    barrier = Barrier(5)

    def deliver(_):
        barrier.wait(timeout=10)
        return send(client, quotation.quotation_id)

    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(deliver, range(5)))
    statuses = [response.status_code for response in responses]
    assert statuses.count(200) == 1
    assert statuses.count(409) == 4
    assert len(sender.calls) == 1
    assert len(records(engine, send_attempts)) == 1


@pytest.mark.parametrize("status,http_status", [("failed", 502), ("unknown", 202)])
def test_unsuccessful_outcome_persists_and_cannot_retry(delivery, engine, status, http_status):
    client, _, sender, quotation = delivery
    sender.result = DeliveryResult(status=status, error_code="synthetic_failure")
    response = send(client, quotation.quotation_id)
    assert response.status_code == http_status
    assert response.json()["status"] == status
    assert records(engine, send_attempts)[0]["status"] == status
    assert records(engine, enquiries)[0]["status"] == status
    assert provider_status(engine) == status
    assert send(client, quotation.quotation_id).status_code == 409
    assert len(sender.calls) == 1


def test_unexpected_sender_error_is_unknown_without_sensitive_details(delivery, engine, caplog):
    client, _, sender, quotation = delivery
    sender.error = RuntimeError("synthetic-secret-private-details")
    response = send(client, quotation.quotation_id)
    assert response.status_code == 202
    assert response.json()["status"] == "unknown"
    assert "synthetic-secret-private-details" not in response.text + caplog.text
    assert records(engine, send_attempts)[0]["status"] == "unknown"
    assert send(client, quotation.quotation_id).status_code == 409
    assert len(sender.calls) == 1


def test_presend_storage_failure_rolls_back_reservation(delivery, engine):
    client, _, sender, quotation = delivery

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.upper().startswith("INSERT INTO SEND_ATTEMPTS"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic failure"))

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        response = send(client, quotation.quotation_id)
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)
    assert response.status_code == 503
    assert sender.calls == []
    assert records(engine, send_attempts) == []
    assert provider_status(engine) == "ready"
    assert send(client, quotation.quotation_id).status_code == 200


def test_final_storage_failure_retains_pending_and_blocks_retry_after_restart(delivery, engine, settings):
    client, provider, sender, quotation = delivery

    def fail_update(connection, cursor, statement, parameters, context, executemany):
        if statement.upper().startswith("UPDATE SEND_ATTEMPTS"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic failure"))

    event.listen(engine, "before_cursor_execute", fail_update)
    try:
        response = send(client, quotation.quotation_id)
    finally:
        event.remove(engine, "before_cursor_execute", fail_update)
    assert response.status_code == 503
    assert response.json()["status"] == "unknown"
    [attempt] = records(engine, send_attempts)
    assert attempt["status"] == "pending"
    assert attempt["id"] == response.json()["attempt_id"]
    assert provider_status(engine) == "reserved"
    assert records(engine, enquiries)[0]["status"] == "unknown"
    assert send(client, quotation.quotation_id).status_code == 409
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              quotation_provider=provider, telegram_sender=sender)) as reopened:
        assert send(reopened, quotation.quotation_id).status_code == 409
        detail = reopened.get(f"/api/enquiries/{quotation.enquiry_id}").json()
        assert detail["status"] == "unknown"
        [visible_attempt] = detail["delivery_attempts"]
        assert visible_attempt["attempt_id"] == attempt["id"]
        assert visible_attempt["status"] == "pending"
        assert visible_attempt["requires_verification"] is True
        assert "pdf_bytes" not in visible_attempt
    assert len(sender.calls) == 1
