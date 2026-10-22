from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.database import telegram_updates
from app.main import create_app

ENDPOINT = "/api/webhooks/telegram"


def stored_rows(engine):
    with engine.connect() as connection:
        return connection.execute(select(telegram_updates)).mappings().all()


def test_receipt_preserves_original_message(client, engine, headers, update):
    response = client.post(ENDPOINT, headers=headers, json=update)
    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    [row] = stored_rows(engine)
    assert row["update_id"] == update["update_id"]
    assert row["message_id"] == update["message"]["message_id"]
    assert row["chat_id"] == update["message"]["chat"]["id"]
    assert row["original_text"] == update["message"]["text"]
    assert row["received_at"] is not None


@pytest.mark.parametrize("secret", [None, "wrong-secret"])
def test_secret_checked_before_json_parsing(client, engine, secret):
    headers = {} if secret is None else {"X-Telegram-Bot-Api-Secret-Token": secret}
    response = client.post(ENDPOINT, headers=headers, content=b"invalid-json")
    assert response.status_code == 401
    assert stored_rows(engine) == []


@pytest.mark.parametrize("body", [b"{", b"\xff", b""])
def test_bad_json(client, engine, headers, body):
    response = client.post(ENDPOINT, headers=headers, content=body)
    assert response.status_code == 400
    assert stored_rows(engine) == []


@pytest.mark.parametrize("path,value", [
    (("update_id",), -1),
    (("update_id",), True),
    (("update_id",), "12345"),
    (("update_id",), 2**63),
    (("message", "message_id"), 0),
    (("message", "chat", "id"), 0),
    (("message", "chat", "id"), -(2**63) - 1),
    (("message", "text"), ""),
    (("message", "text"), " \n "),
    (("message", "text"), "x" * 4097),
    (("message", "text"), "private-null\x00"),
    (("message", "text"), 42),
])
def test_invalid_message_is_not_saved(client, engine, headers, update, path, value):
    target = update
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    response = client.post(ENDPOINT, headers=headers, json=update)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid Telegram update"}
    assert stored_rows(engine) == []


@pytest.mark.parametrize("payload", [{}, [], None, {"update_id": 1, "message": {}}])
def test_invalid_top_level_schema(client, headers, payload):
    import json

    response = client.post(ENDPOINT, headers=headers, content=json.dumps(payload))
    assert response.status_code == 422


@pytest.mark.parametrize("kind", ["photo", "edited_message", "callback_query"])
def test_unsupported_update_is_ignored(client, engine, headers, update, kind):
    if kind == "photo":
        del update["message"]["text"]
        update["message"]["photo"] = [{"file_id": "synthetic"}]
    else:
        update[kind] = update.pop("message")
    response = client.post(ENDPOINT, headers=headers, json=update)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert stored_rows(engine) == []


def test_duplicate_cannot_replace_original(client, engine, headers, update):
    assert client.post(ENDPOINT, headers=headers, json=update).json()["status"] == "received"
    replacement = deepcopy(update)
    replacement["message"]["text"] = "replacement must not be stored"
    replacement["message"]["chat"]["id"] = 123
    response = client.post(ENDPOINT, headers=headers, json=replacement)
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}
    [row] = stored_rows(engine)
    assert row["original_text"] == update["message"]["text"]
    assert row["chat_id"] == update["message"]["chat"]["id"]


def test_concurrent_duplicates_store_exactly_once(client, engine, headers, update):
    barrier = Barrier(6)

    def deliver(_):
        barrier.wait(timeout=10)
        return client.post(ENDPOINT, headers=headers, json=update)

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(deliver, range(6)))
    assert all(response.status_code == 200 for response in responses)
    statuses = [response.json()["status"] for response in responses]
    assert statuses.count("received") == 1
    assert statuses.count("duplicate") == 5
    assert len(stored_rows(engine)) == 1


def test_duplicate_survives_app_and_connection_restart(engine, settings, headers, update):
    with TestClient(create_app(settings, engine)) as first:
        assert first.post(ENDPOINT, headers=headers, json=update).json()["status"] == "received"
    engine.dispose()
    with TestClient(create_app(settings, engine)) as reopened:
        response = reopened.post(ENDPOINT, headers=headers, json=update)
        assert response.status_code == 200
        assert response.json() == {"status": "duplicate"}
    assert len(stored_rows(engine)) == 1


def test_database_failure_is_retryable_without_leaking_data(client, engine, headers, update, caplog):
    sensitive = "synthetic-password-and-private-query"

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            raise OperationalError(statement, parameters, RuntimeError(sensitive))

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        response = client.post(ENDPOINT, headers=headers, json=update)
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)
    assert response.status_code == 503
    assert sensitive not in response.text + caplog.text
    assert update["message"]["text"] not in response.text + caplog.text
    assert stored_rows(engine) == []
    assert client.post(ENDPOINT, headers=headers, json=update).json() == {"status": "received"}


def test_oversized_stream_without_content_length(client, engine, headers):
    def chunks():
        yield b" " * (32 * 1024)
        yield b" " * (32 * 1024 + 1)

    response = client.post(ENDPOINT, headers=headers, content=chunks())
    assert response.status_code == 413
    assert stored_rows(engine) == []
