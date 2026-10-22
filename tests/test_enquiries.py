from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import backfill_enquiries, enquiries, metadata, telegram_updates
from app.main import create_app

WEBHOOK = "/api/webhooks/telegram"
INBOX = "/api/enquiries"


def rows(engine, table):
    with engine.connect() as connection:
        return connection.execute(select(table)).mappings().all()


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_received_message_has_enquiry_and_original_detail(client, headers, update):
    update["message"]["chat"]["id"] = -(2**53 + 11)
    update["update_id"] = 2**53 + 13
    update["message"]["message_id"] = 2**53 + 17
    assert client.post(WEBHOOK, headers=headers, json=update).json()["status"] == "received"
    response = client.get(INBOX)
    assert response.status_code == 200
    result = response.json()
    assert result["limit"] == 50
    assert result["offset"] == 0
    [summary] = result["items"]
    assert str(UUID(summary["id"])) == summary["id"]
    assert summary["source"] == "telegram"
    assert summary["status"] == "needs_review"
    assert summary["telegram_chat_id"] == str(update["message"]["chat"]["id"])
    assert summary["original_text"] == update["message"]["text"]
    assert timestamp(summary["created_at"]).utcoffset().total_seconds() == 0
    detail_response = client.get(f"{INBOX}/{summary['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert {key: detail[key] for key in summary} == summary
    [message] = detail["messages"]
    assert message["update_id"] == str(update["update_id"])
    assert message["message_id"] == str(update["message"]["message_id"])
    assert message["chat_id"] == str(update["message"]["chat"]["id"])
    assert message["text"] == update["message"]["text"]
    assert timestamp(message["received_at"]) == timestamp(summary["created_at"])


def test_same_chat_distinct_updates_create_distinct_enquiries(client, engine, headers, update):
    second = deepcopy(update)
    second["update_id"] += 1
    second["message"]["message_id"] += 1
    second["message"]["text"] = "Another fictional request"
    for payload in (update, second):
        assert client.post(WEBHOOK, headers=headers, json=payload).status_code == 200
    items = client.get(INBOX).json()["items"]
    assert len(items) == 2
    assert len({item["id"] for item in items}) == 2
    assert len({item["telegram_chat_id"] for item in items}) == 1
    assert {item["original_text"] for item in items} == {
        update["message"]["text"], second["message"]["text"]
    }
    assert len(rows(engine, enquiries)) == 2


@pytest.mark.parametrize("error_type", [OperationalError, IntegrityError])
def test_enquiry_insert_failure_rolls_back_receipt(client, engine, headers, update, error_type):
    def fail_enquiry(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO ENQUIRIES"):
            original = RuntimeError("synthetic-private-db-error")
            # A separate table's PK violation must not be mistaken for a receipt duplicate.
            original.sqlite_errorcode = 1555
            raise error_type(statement, parameters, original)

    event.listen(engine, "before_cursor_execute", fail_enquiry)
    try:
        response = client.post(WEBHOOK, headers=headers, json=update)
    finally:
        event.remove(engine, "before_cursor_execute", fail_enquiry)
    assert response.status_code == 503
    assert "synthetic-private-db-error" not in response.text
    assert rows(engine, telegram_updates) == []
    assert rows(engine, enquiries) == []
    assert client.post(WEBHOOK, headers=headers, json=update).json()["status"] == "received"
    assert len(rows(engine, enquiries)) == 1


def test_concurrent_duplicates_create_exactly_one_enquiry(client, engine, headers, update):
    barrier = Barrier(6)

    def deliver(_):
        barrier.wait(timeout=10)
        return client.post(WEBHOOK, headers=headers, json=update)

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(deliver, range(6)))
    assert all(response.status_code == 200 for response in responses)
    assert [response.json()["status"] for response in responses].count("received") == 1
    assert len(rows(engine, telegram_updates)) == 1
    assert len(rows(engine, enquiries)) == 1


def test_enquiry_survives_restart_without_duplicate(engine, settings, headers, update):
    with TestClient(create_app(settings, engine)) as first:
        first.post(WEBHOOK, headers=headers, json=update)
        original = first.get(INBOX).json()["items"][0]
    engine.dispose()
    with TestClient(create_app(settings, engine)) as reopened:
        assert reopened.get(INBOX).json()["items"] == [original]
        assert reopened.post(WEBHOOK, headers=headers, json=update).json()["status"] == "duplicate"
        assert reopened.get(f"{INBOX}/{original['id']}").status_code == 200
    assert len(rows(engine, enquiries)) == 1


def seed_legacy_receipts(engine):
    metadata.create_all(engine)
    original_time = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(telegram_updates.insert(), [
            {"update_id": number, "message_id": number + 100, "chat_id": -1001234567890,
             "original_text": f"Fictional legacy enquiry {number}", "received_at": original_time}
            for number in (1, 2, 3)
        ])
    return original_time


def test_startup_backfill_is_idempotent_and_preserves_status(engine, settings):
    original_time = seed_legacy_receipts(engine)
    with TestClient(create_app(settings, engine)) as client:
        items = client.get(INBOX).json()["items"]
        assert len(items) == 3
        assert all(timestamp(item["created_at"]) == original_time for item in items)
    first_id = items[0]["id"]
    with engine.begin() as connection:
        connection.execute(enquiries.update().where(enquiries.c.id == first_id).values(status="sent"))
    backfill_enquiries(engine)
    with TestClient(create_app(settings, engine)) as client:
        after = client.get(INBOX).json()["items"]
        assert {item["id"] for item in after} == {item["id"] for item in items}
        assert client.get(f"{INBOX}/{first_id}").json()["status"] == "sent"
        assert all(timestamp(item["created_at"]) == original_time for item in after)


def test_concurrent_backfill_creates_one_enquiry_per_receipt(engine):
    seed_legacy_receipts(engine)
    barrier = Barrier(3)

    def backfill(_):
        barrier.wait(timeout=10)
        backfill_enquiries(engine)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(backfill, range(3)))
    records = rows(engine, enquiries)
    assert len(records) == 3
    assert {record["telegram_update_id"] for record in records} == {1, 2, 3}


def test_inbox_pagination_has_stable_timestamp_and_id_order(client, engine, headers, update):
    for number in range(3):
        payload = deepcopy(update)
        payload["update_id"] += number
        client.post(WEBHOOK, headers=headers, json=payload)
    records = rows(engine, enquiries)
    old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    new_time = datetime(2025, 1, 2, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(enquiries.update().values(created_at=new_time))
        connection.execute(enquiries.update().where(enquiries.c.id == records[0]["id"]).values(created_at=old_time))
    expected_ids = sorted((row["id"] for row in records[1:]), reverse=True) + [records[0]["id"]]
    all_items = client.get(INBOX).json()["items"]
    assert [item["id"] for item in all_items] == expected_ids
    page = client.get(INBOX, params={"limit": 1, "offset": 1}).json()
    assert page == {"items": [all_items[1]], "limit": 1, "offset": 1}
    assert client.get(INBOX, params={"offset": 3}).json()["items"] == []


@pytest.mark.parametrize("query", [
    "limit=0", "limit=101", "limit=x", "offset=-1", "offset=x",
    f"offset={2**63}",
])
def test_invalid_pagination(client, query):
    assert client.get(f"{INBOX}?{query}").status_code == 422


def test_empty_inbox_and_missing_detail(client):
    assert client.get(INBOX).json() == {"items": [], "limit": 50, "offset": 0}
    assert client.get(f"{INBOX}/{uuid4()}").status_code == 404
    assert client.get(f"{INBOX}/not-a-uuid").status_code == 422


@pytest.mark.parametrize("path", [INBOX, f"{INBOX}/00000000-0000-0000-0000-000000000001"])
def test_read_database_failure_is_safe(client, engine, caplog, path):
    def fail_read(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic-private-db-error"))

    event.listen(engine, "before_cursor_execute", fail_read)
    try:
        response = client.get(path)
    finally:
        event.remove(engine, "before_cursor_execute", fail_read)
    assert response.status_code == 503
    assert "synthetic-private-db-error" not in response.text + caplog.text
