from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.database import outgoing_messages
from app.main import create_app
from app.telegram_client import DeliveryResult, TelegramSender
from tests.test_routing_v2 import receive


class TextSender:
    def __init__(self):
        self.calls = []
        self.result = DeliveryResult("sent", message_id="9999")

    def send_text(self, chat, content):
        self.calls.append((chat, content))
        return self.result


@pytest.fixture
def room(engine, settings, headers, update):
    sender = TextSender()
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              telegram_sender=sender)) as client:
        receive(client, headers, update, 0, "Synthetic request for a quotation")
        [enquiry] = client.get("/api/enquiries").json()["items"]
        yield client, sender, enquiry


def send(room, patch=None, actor="sales"):
    client, _, enquiry = room
    return client.post(f"/api/enquiries/{enquiry['id']}/messages",
                       headers={"X-Demo-Actor": actor} if actor else {},
                       json=patch or {"text": "Please confirm the required size.", "request_id": str(uuid4())})


def test_staff_reply_has_explicit_author_original_chat_and_chronology(room, update):
    client, sender, enquiry = room
    response = send(room)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert sender.calls == [(update["message"]["chat"]["id"], "Please confirm the required size.")]
    items = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()["items"]
    assert [m["direction"] for m in items] == ["incoming", "outgoing"]
    assert items[0]["actor"] == "customer" and items[1]["actor"] == "sales"
    assert items[1]["text"] == "Please confirm the required size."
    assert items[1]["created_at"].endswith("+00:00")


@pytest.mark.parametrize("actor,status", [(None, 403), ("ai", 401), ("customer", 401)])
def test_ai_and_unauthorized_requests_cannot_send(room, actor, status):
    assert send(room, actor=actor).status_code == status
    assert room[1].calls == []


@pytest.mark.parametrize("patch", [{"text": "", "request_id": str(uuid4())},
                                     {"text": "Hello", "request_id": "invalid"},
                                     {"text": "Hello", "request_id": str(uuid4()), "chat_id": 123},
                                     {"text": "x" * 4001, "request_id": str(uuid4())}])
def test_recipient_override_and_invalid_text_rejected(room, patch):
    assert send(room, patch).status_code == 422
    assert room[1].calls == []


@pytest.mark.parametrize("outcome,status", [("sent", 200), ("failed", 502), ("unknown", 202)])
def test_delivery_outcome_and_replayed_request_do_not_duplicate(room, outcome, status):
    client, sender, enquiry = room
    sender.result = DeliveryResult(outcome, message_id="9999" if outcome == "sent" else None,
                                   error_code="telegram_403" if outcome == "failed" else None)
    patch = {"text": "Please confirm quantity", "request_id": str(uuid4())}
    assert send(room, patch).status_code == status
    assert send(room, patch).status_code == status
    assert len(sender.calls) == 1
    assert send(room, {**patch, "text": "Different content"}).status_code == 409
    outgoing = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()["items"][-1]
    assert outgoing["status"] == outcome


def test_wrong_profile_cannot_read_or_send(room):
    client, sender, enquiry = room
    client.patch("/api/business-profiles/active", json={"business_profile_id": "repair"})
    assert send(room).status_code == 404
    assert client.get(f"/api/enquiries/{enquiry['id']}/conversation").status_code == 404
    assert sender.calls == []


def test_customer_reply_to_staff_message_targets_correct_enquiry(room, headers, update):
    client, _, enquiry = room
    assert send(room).status_code == 200
    receive(client, headers, update, 1, "New quotation for a separate job")
    receive(client, headers, update, 2, "Yes, blue", reply=9999)
    messages = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()["items"]
    assert [m["direction"] for m in messages] == ["incoming", "outgoing", "incoming"]
    assert messages[-1]["text"] == "Yes, blue"


def test_outcome_storage_failure_keeps_pending_hold(room, engine):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE OUTGOING_MESSAGES"):
            raise OperationalError(statement, parameters, RuntimeError("synthetic failure"))
    patch = {"text": "Please confirm quantity", "request_id": str(uuid4())}
    event.listen(engine, "before_cursor_execute", fail)
    try:
        response = send(room, patch)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == 202 and response.json()["status"] == "unknown"
    with engine.connect() as connection:
        assert connection.execute(select(outgoing_messages.c.status)).scalar_one() == "pending"
    assert send(room, patch).json()["status"] == "pending"
    assert len(room[1].calls) == 1


def test_text_transport_uses_one_shot_sendmessage_with_safe_result():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 123, "chat": {"id": -500}}})
    result = TelegramSender("synthetic-token", httpx.MockTransport(handler)).send_text(-500, "Synthetic clarification")
    assert result == DeliveryResult("sent", message_id="123")
    assert len(seen) == 1 and seen[0].url.path.endswith("/sendMessage")
