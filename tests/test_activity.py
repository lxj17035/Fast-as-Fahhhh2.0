"""Canonical history follows committed operations, including audit-write failures."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.database import enquiries, metadata, send_attempts, telegram_updates
from app.main import create_app
from backend.store import records as xinjie_records
from app.telegram_client import DeliveryResult
from tests.test_xinjie_integration import (
    RecordingTelegram, deliver, draft, edit, integrated, preview, ready,
)


def history(client, enquiry):
    response = client.get(f"/api/enquiries/{enquiry['id']}")
    assert response.status_code == 200
    return response.json()["activity"]


def actions(client, enquiry):
    return Counter(item["action"] for item in history(client, enquiry))


def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


@contextmanager
def fail_activity(engine, action):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if not statement.lstrip().upper().startswith("INSERT INTO ACTIVITIES"):
            return
        values = context.compiled_parameters or []
        if any(value.get("action") == action for value in values):
            raise OperationalError(statement, parameters, RuntimeError("synthetic-private-audit-error"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", fail)


def test_full_activity_history_has_real_references_and_safe_fields(integrated, update):
    client, _, enquiry = integrated
    quotation = ready(client, enquiry)
    assert preview(client, quotation).status_code == 200
    result = deliver(client, quotation)
    assert result.status_code == 200
    events = history(client, enquiry)
    assert Counter(item["action"] for item in events) == Counter({
        "telegram_received": 1, "enquiry_created": 1, "quotation_draft_created": 1,
        "quotation_updated": 1, "pm_approved": 1, "pdf_send_attempted": 1,
        "pdf_send_succeeded": 1,
    })
    assert len({item["id"] for item in events}) == len(events)
    timestamps = [datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")) for item in events]
    assert timestamps == sorted(timestamps)
    assert all(value.utcoffset().total_seconds() == 0 for value in timestamps)
    for item in events:
        assert item["enquiry_id"] == enquiry["id"]
        assert item["result"]
        assert item["actor_origin"] in {"system", "simulated", "unknown"}
    by_action = {item["action"]: item for item in events}
    for name in ("pm_approved", "pdf_send_attempted", "pdf_send_succeeded"):
        item = by_action[name]
        assert item["attempt_id"] == result.json()["attempt_id"]
        assert item["version"] == quotation["version"]
        assert item["quotation_id"].replace("-", "") == quotation["id"]
    assert by_action["pm_approved"]["actor_id"] == "pm"
    assert by_action["pm_approved"]["role"] == "pm"
    assert by_action["pm_approved"]["actor_origin"] == "simulated"
    assert by_action["pdf_send_succeeded"]["provider_reference"] == "87654321"
    assert by_action["quotation_updated"]["actor_id"] == "pm"
    assert by_action["quotation_updated"]["role"] == "pm"
    assert by_action["quotation_updated"]["actor_origin"] == "simulated"
    serialized = json.dumps(events)
    assert update["message"]["text"] not in serialized
    assert "synthetic-test-secret" not in serialized
    assert "synthetic-test-bot-token" not in serialized
    assert "%PDF-" not in serialized


@pytest.mark.parametrize("actor", ["pm", "sales"])
def test_update_records_explicit_simulated_actor(integrated, actor):
    client, _, enquiry = integrated
    quotation = draft(client, enquiry)
    response = client.patch(f"/api/quotations/{quotation['id']}",
                            headers={"X-Demo-Actor": actor},
                            json={"version": 1, "notes": "Fictional revision"})
    assert response.status_code == 200
    [updated] = [item for item in history(client, enquiry) if item["action"] == "quotation_updated"]
    assert updated["actor_id"] == actor
    assert updated["role"] == actor
    assert updated["actor_origin"] == "simulated"


def test_invalid_or_disabled_actor_header_cannot_mutate(integrated, engine, settings):
    client, _, enquiry = integrated
    quotation = draft(client, enquiry)
    path = f"/api/quotations/{quotation['id']}"
    assert client.patch(path, headers={"X-Demo-Actor": "invented"},
                        json={"version": 1, "notes": "forbidden"}).status_code == 401
    with TestClient(create_app(settings, engine)) as disabled:
        assert disabled.patch(path, headers={"X-Demo-Actor": "pm"},
                              json={"version": 1, "notes": "forbidden"}).status_code == 503
    assert client.get(path).json()["version"] == 1
    assert actions(client, enquiry)["quotation_updated"] == 0


def test_receipt_audit_failure_rolls_back_receipt_and_enquiry(client, engine, headers, update):
    with fail_activity(engine, "enquiry_created"):
        assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 503
    assert rows(engine, telegram_updates) == []
    assert rows(engine, enquiries) == []
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    enquiry = client.get("/api/enquiries").json()["items"][0]
    assert actions(client, enquiry) == Counter(telegram_received=1, enquiry_created=1, quotation_draft_created=1)


def test_draft_audit_failure_rolls_back_quote_and_leaves_no_legacy_log(integrated, engine):
    client, _, enquiry = integrated
    # Remove the existing auto draft to exercise an explicit retry after interruption.
    with engine.begin() as connection:
        connection.execute(xinjie_records.delete().where(xinjie_records.c.kind == "quotations"))
        from app.database import activities
        connection.execute(activities.delete().where(activities.c.action == "quotation_draft_created"))
    with fail_activity(engine, "quotation_draft_created"):
        response = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True})
    assert response.status_code == 503
    assert not [row for row in rows(engine, xinjie_records) if row["kind"] in {"quotations", "activity"}]
    assert actions(client, enquiry) == Counter(telegram_received=1, enquiry_created=1)
    draft(client, enquiry)
    assert actions(client, enquiry)["quotation_draft_created"] == 1
    assert not [row for row in rows(engine, xinjie_records) if row["kind"] == "activity"]


def test_update_audit_failure_rolls_back_version(integrated, engine):
    client, _, enquiry = integrated
    quotation = draft(client, enquiry)
    with fail_activity(engine, "quotation_updated"):
        response = edit(client, quotation, notes="Must roll back")
    assert response.status_code == 503
    saved = client.get(f"/api/quotations/{quotation['id']}").json()
    assert saved == quotation
    assert actions(client, enquiry)["quotation_updated"] == 0


@pytest.mark.parametrize("action", ["pm_approved", "pdf_send_attempted"])
def test_approval_audit_failure_prevents_network_and_rolls_back_reservation(integrated, engine, action):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert preview(client, quotation).status_code == 200
    with fail_activity(engine, action):
        response = deliver(client, quotation)
    assert response.status_code == 503
    assert sender.calls == []
    assert rows(engine, send_attempts) == []
    assert client.get(f"/api/quotations/{quotation['id']}").json()["status"] == "draft"
    assert actions(client, enquiry)["pm_approved"] == 0
    assert actions(client, enquiry)["pdf_send_attempted"] == 0
    assert deliver(client, quotation).status_code == 200


def test_outcome_audit_failure_keeps_pending_without_false_success(integrated, engine):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    assert preview(client, quotation).status_code == 200
    with fail_activity(engine, "pdf_send_succeeded"):
        response = deliver(client, quotation)
    assert response.status_code == 503
    assert response.json()["status"] == "unknown"
    assert len(sender.calls) == 1
    [attempt] = rows(engine, send_attempts)
    assert attempt["status"] == "pending"
    assert client.get(f"/api/quotations/{quotation['id']}").json()["status"] == "sending"
    assert client.get(f"/api/enquiries/{enquiry['id']}").json()["status"] == "unknown"
    counts = actions(client, enquiry)
    assert counts["pm_approved"] == counts["pdf_send_attempted"] == 1
    assert counts["pdf_send_succeeded"] == counts["pdf_send_failed"] == counts["delivery_unknown"] == 0
    assert deliver(client, quotation).status_code == 409


@pytest.mark.parametrize("status,action,http_status", [
    ("failed", "pdf_send_failed", 502), ("unknown", "delivery_unknown", 202),
])
def test_unsuccessful_outcome_logs_only_safe_actual_result(integrated, status, action, http_status):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    preview(client, quotation)
    sender.result = DeliveryResult(status, error_code="raw-secret-from-provider")
    assert deliver(client, quotation).status_code == http_status
    events = history(client, enquiry)
    assert Counter(item["action"] for item in events)[action] == 1
    assert not any(item["action"] == "pdf_send_succeeded" for item in events)
    assert "raw-secret-from-provider" not in json.dumps(events)


def test_restart_duplicates_and_concurrent_send_keep_one_event_sequence(integrated, engine, settings, headers, update):
    client, sender, enquiry = integrated
    quotation = ready(client, enquiry)
    preview(client, quotation)
    for _ in range(2):
        assert client.post("/api/webhooks/telegram", headers=headers, json=update).json()["status"] == "duplicate"
        assert draft(client, enquiry)["id"] == quotation["id"]
    barrier = Barrier(4)

    def send(_):
        barrier.wait(timeout=10)
        return deliver(client, quotation)

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(send, range(4)))
    assert [response.status_code for response in responses].count(200) == 1
    assert len(sender.calls) == 1
    before = history(client, enquiry)
    assert all(count == 1 for count in Counter(item["action"] for item in before).values())
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              telegram_sender=RecordingTelegram())) as reopened:
        assert history(reopened, enquiry) == before
        assert deliver(reopened, quotation).status_code == 409
        assert history(reopened, enquiry) == before


def test_history_is_scoped_to_its_enquiry(integrated, headers, update):
    client, _, first = integrated
    second_update = deepcopy(update)
    second_update["update_id"] += 1
    second_update["message"]["chat"]["id"] += 1
    assert client.post("/api/webhooks/telegram", headers=headers, json=second_update).status_code == 200
    [second] = [item for item in client.get("/api/enquiries").json()["items"] if item["id"] != first["id"]]
    draft(client, first)
    assert actions(client, second) == Counter(telegram_received=1, enquiry_created=1, quotation_draft_created=1)
    assert {item["id"] for item in history(client, first)}.isdisjoint(
        item["id"] for item in history(client, second))


def test_legacy_receipt_backfill_does_not_invent_history(engine, settings):
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(telegram_updates.insert().values(
            update_id=9191, message_id=9192, chat_id=-1001234567890,
            original_text="Fictional legacy receipt",
            received_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        ))
    with TestClient(create_app(settings, engine)) as client:
        [enquiry] = client.get("/api/enquiries").json()["items"]
        assert history(client, enquiry) == []
