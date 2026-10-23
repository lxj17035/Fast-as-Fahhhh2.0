"""Real quotation/PDF retry flow with mocked Telegram and isolated databases."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import OperationalError

from app.database import send_attempts
from app.main import create_app
from app.telegram_client import DeliveryResult
from tests.test_xinjie_integration import integrated, ready, preview, deliver, RecordingTelegram


def attempts(client, enquiry):
    return client.get(f"/api/enquiries/{enquiry['id']}").json()["delivery_attempts"]


def retry(client, quote, failed_id, *, actor="pm", **extra):
    return client.post(f"/api/quotations/{quote['id']}/send",
        headers={"X-Demo-Actor": actor}, json={"expected_version": quote["version"],
        "approved": True, "retry_of_attempt_id": failed_id, **extra})


def failed(integrated):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    sender.result = DeliveryResult("failed", error_code="telegram_403")
    response = deliver(client, quote)
    assert response.status_code == 502
    return client, sender, enquiry, quote, pdf, response.json()["attempt_id"]


def test_confirmed_failure_needs_fresh_approval_and_preserves_each_attempt(integrated, engine, update):
    client, sender, enquiry, quote, pdf, first = failed(integrated)
    assert attempts(client, enquiry)[0]["can_retry"] is True
    assert deliver(client, quote).status_code == 409
    assert retry(client, quote, first, actor="sales").status_code == 403
    assert retry(client, quote, first, approved=False).status_code == 422
    assert retry(client, quote, str(uuid4())).status_code == 409
    sender.result = DeliveryResult("sent", message_id="123456")
    response = retry(client, quote, first)
    assert response.status_code == 200, response.text
    second = response.json()["attempt_id"]
    assert second != first
    assert sender.calls == [(update["message"]["chat"]["id"], pdf)] * 2
    by_id = {a["attempt_id"]: a for a in attempts(client, enquiry)}
    assert by_id[first]["status"] == "failed"
    assert by_id[second]["retry_of_attempt_id"] == first
    assert by_id[second]["status"] == "sent"
    assert not any(a["can_retry"] for a in by_id.values())
    assert retry(client, quote, first).status_code == 409
    assert retry(client, quote, second).status_code == 409
    assert len(sender.calls) == 2
    with engine.connect() as connection:
        rows = connection.execute(select(send_attempts)).mappings().all()
    assert len(rows) == 2 and all(r["pdf_bytes"] == pdf for r in rows)
    history = client.get(f"/api/enquiries/{enquiry['id']}").json()["activity"]
    approvals = [a for a in history if a["action"] == "pm_approved"]
    assert {a["attempt_id"] for a in approvals} == {first, second}


def test_repeated_failure_requires_the_new_failed_attempt_id(integrated):
    client, sender, enquiry, quote, _, first = failed(integrated)
    second_response = retry(client, quote, first)
    assert second_response.status_code == 502
    second = second_response.json()["attempt_id"]
    assert retry(client, quote, first).status_code == 409
    by_id = {a["attempt_id"]: a for a in attempts(client, enquiry)}
    assert not by_id[first]["can_retry"] and by_id[second]["can_retry"]
    sender.result = DeliveryResult("sent", message_id="123456")
    assert retry(client, quote, second).status_code == 200
    assert len(sender.calls) == 3


@pytest.mark.parametrize("outcome,code", [("sent", 200), ("unknown", 202)])
def test_sent_or_unknown_cannot_be_retried(integrated, outcome, code):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.result = DeliveryResult(outcome, message_id="123456" if outcome == "sent" else None)
    result = deliver(client, quote)
    assert result.status_code == code
    assert retry(client, quote, result.json()["attempt_id"]).status_code == 409
    assert not attempts(client, enquiry)[0]["can_retry"]
    assert len(sender.calls) == 1


def test_retry_without_previous_failure_and_cross_quote_id_are_rejected(integrated):
    client, sender, _, quote, _, first = failed(integrated)
    second_enquiry = client.post("/api/demo/enquiries", json={"text": "Other fictional enquiry"}).json()
    other = client.post(f"/api/enquiries/{second_enquiry['id']}/draft", json={"manual": True}).json()
    assert retry(client, other, first).status_code == 409
    assert retry(client, quote, "not-a-uuid").status_code == 422
    assert len(sender.calls) == 1


def test_retry_after_edit_needs_current_version_and_new_preview(integrated):
    client, sender, enquiry, quote, _, first = failed(integrated)
    updated = client.patch(f"/api/quotations/{quote['id']}", json={
        "version": quote["version"], "notes": "PM corrected quotation"}).json()
    assert retry(client, quote, first).status_code == 409
    assert retry(client, updated, first).status_code == 409
    new_pdf = preview(client, updated).content
    sender.result = DeliveryResult("sent", message_id="123456")
    assert retry(client, updated, first).status_code == 200
    assert sender.calls[-1][1] == new_pdf
    assert attempts(client, enquiry)[-1]["version"] == updated["version"]


def test_concurrent_and_in_flight_retry_upload_only_once(integrated):
    client, sender, enquiry, quote, _, first = failed(integrated)
    sender.result = DeliveryResult("sent", message_id="123456")
    sender.entered, sender.release = Event(), Event()
    barrier = Barrier(3)
    def submit():
        barrier.wait(timeout=10)
        return retry(client, quote, first)
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(submit) for _ in range(3)]
        try:
            assert sender.entered.wait(timeout=10)
            assert retry(client, quote, first).status_code == 409
            assert not any(a["can_retry"] for a in attempts(client, enquiry))
        finally:
            sender.release.set()
        assert sorted(j.result(timeout=15).status_code for j in jobs) == [200, 409, 409]
    assert len(sender.calls) == 2
    assert len(attempts(client, enquiry)) == 2


def test_failed_approval_log_rolls_back_retry_and_keeps_it_available(integrated, engine):
    client, sender, enquiry, quote, _, first = failed(integrated)
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO ACTIVITIES") and any(
            p.get("action") == "pm_approved" for p in context.compiled_parameters or []):
            raise OperationalError(statement, parameters, RuntimeError("synthetic-private-error"))
    event.listen(engine, "before_cursor_execute", fail)
    try:
        response = retry(client, quote, first)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == 503
    assert "synthetic-private-error" not in response.text
    assert len(sender.calls) == 1 and len(attempts(client, enquiry)) == 1
    assert attempts(client, enquiry)[0]["can_retry"]
    sender.result = DeliveryResult("sent", message_id="123456")
    assert retry(client, quote, first).status_code == 200


def test_retry_survives_restart_and_replayed_approval_is_blocked(integrated, engine, settings):
    client, _, enquiry, quote, _, first = failed(integrated)
    sender = RecordingTelegram()
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              telegram_sender=sender)) as reopened:
        assert retry(reopened, quote, first).status_code == 200
        assert retry(reopened, quote, first).status_code == 409
        assert len(attempts(reopened, enquiry)) == 2
    assert len(sender.calls) == 1


def test_existing_postgres_schema_upgrades_without_losing_failure_history(integrated, engine, settings):
    if engine.dialect.name != "postgresql":
        pytest.skip("Legacy runtime schema upgrade requires PostgreSQL")
    client, sender, enquiry, quote, pdf, first = failed(integrated)
    original_history = client.get(f"/api/enquiries/{enquiry['id']}").json()["activity"]
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX send_attempts_initial_unique"))
        connection.execute(text("DROP INDEX send_attempts_retry_unique"))
        connection.execute(text("ALTER TABLE send_attempts DROP COLUMN retry_of_attempt_id"))
        connection.execute(text("ALTER TABLE send_attempts ADD CONSTRAINT send_attempts_quotation_id_key UNIQUE (quotation_id)"))
    sender.result = DeliveryResult("sent", message_id="123456")
    for _ in range(2):  # Upgrade is safe across repeated startup.
        with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                                  telegram_sender=sender)) as reopened:
            assert attempts(reopened, enquiry)[0]["can_retry"]
            assert reopened.get(f"/api/enquiries/{enquiry['id']}").json()["activity"] == original_history
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              telegram_sender=sender)) as reopened:
        assert retry(reopened, quote, first).status_code == 200
        assert len(attempts(reopened, enquiry)) == 2
    assert sender.calls[-1][1] == pdf
    assert not any(c["column_names"] == ["quotation_id"] for c in inspect(engine).get_unique_constraints("send_attempts"))


def test_retry_outcome_save_failure_leaves_pending_and_blocks_further_upload(integrated, engine):
    client, sender, enquiry, quote, _, first = failed(integrated)
    sender.result = DeliveryResult("sent", message_id="123456")
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE SEND_ATTEMPTS"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic-private-outcome"))
    event.listen(engine, "before_cursor_execute", fail)
    try:
        result = retry(client, quote, first)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert result.status_code == 503 and result.json()["status"] == "unknown"
    assert retry(client, quote, first).status_code == 409
    assert retry(client, quote, result.json()["attempt_id"]).status_code == 409
    assert not any(a["can_retry"] for a in attempts(client, enquiry))
    assert len(sender.calls) == 2
