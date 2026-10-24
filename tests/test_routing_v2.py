from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import message_links, telegram_updates
from app.main import create_app
from app.routing import assign_message
from app.xinjie_store import Store
from backend.errors import AppError


def receive(client, headers, update, number, content, reply=None):
    value = deepcopy(update)
    value["update_id"] += number
    value["message"]["message_id"] += number
    value["message"]["text"] = content
    if reply:
        value["message"]["reply_to_message"] = {"message_id": reply}
    response = client.post("/api/webhooks/telegram", headers=headers, json=value)
    assert response.status_code == 200, response.text
    return value


@pytest.mark.parametrize("command", ["/start", "/help", "/start@DemoBot", "/help more"])
def test_commands_remain_receipts_without_creating_quotes(client, engine, headers, update, command):
    receive(client, headers, update, 0, command)
    assert client.get("/api/enquiries").json()["items"] == []
    assert client.app.state.quotation_app.store.list("quotations") == []
    with engine.connect() as connection:
        assert connection.execute(select(message_links.c.status)).scalar_one() == "command"
        assert connection.execute(select(telegram_updates.c.original_text)).scalar_one() == command


def test_followup_joins_one_enquiry_and_distinct_order_stays_separate(client, headers, update):
    receive(client, headers, update, 0, "Please quote 1000 flyers")
    first = client.get("/api/enquiries").json()["items"][0]
    receive(client, headers, update, 1, "Actually 1500 flyers, colour blue")
    [item] = client.get("/api/enquiries").json()["items"]
    assert item["id"] == first["id"]
    detail = client.get(f"/api/enquiries/{first['id']}").json()
    assert [m["text"] for m in detail["messages"]] == ["Please quote 1000 flyers", "Actually 1500 flyers, colour blue"]
    receive(client, headers, update, 2, "New quotation for a separate order")
    assert len(client.get("/api/enquiries").json()["items"]) == 2


def test_reply_reference_disambiguates_same_chat_orders(client, headers, update):
    receive(client, headers, update, 0, "Printing request one")
    receive(client, headers, update, 1, "New quotation request two")
    first = next(i for i in client.get("/api/enquiries").json()["items"] if i["original_text"] == "Printing request one")
    receive(client, headers, update, 2, "Confirm quantity 1500", reply=update["message"]["message_id"])
    assert len(client.get(f"/api/enquiries/{first['id']}").json()["messages"]) == 2
    assert client.get("/api/assignments").json()["items"] == []


@pytest.mark.parametrize("action", ["assign", "new", "unrelated"])
def test_staff_resolves_ambiguity_with_history_and_cannot_be_overridden(client, engine, settings, headers, update, action):
    client.app.state.settings = replace(settings, enable_demo_approval=True)
    receive(client, headers, update, 0, "Please quote a printing job")
    first = client.get("/api/enquiries").json()["items"][0]
    ambiguous = receive(client, headers, update, 1, "What about this one?")
    [pending] = client.get("/api/assignments").json()["items"]
    assert pending["text"] == "What about this one?"
    path = f"/api/assignments/{ambiguous['update_id']}"
    patch = {"action": action}
    if action == "assign":
        patch["enquiry_id"] = first["id"]
    assert client.post(path, json=patch).status_code == 403
    result = client.post(path, headers={"X-Demo-Actor": "sales"}, json=patch)
    assert result.status_code == 200, result.text
    assert result.json()["history"][-1]["actor"] == "sales"
    assert client.get("/api/assignments").json()["items"] == []
    with pytest.raises(AppError) as error:
        assign_message(Store(engine), ambiguous["update_id"], {"action": "assign", "enquiry_id": first["id"]},
                       "system", origin="ai")
    assert error.value.status == 409


def test_assignment_rejects_foreign_chat_and_profile(client, engine, settings, headers, update):
    client.app.state.settings = replace(settings, enable_demo_approval=True)
    receive(client, headers, update, 0, "Original request")
    first = client.get("/api/enquiries").json()["items"][0]
    ambiguous = receive(client, headers, update, 1, "Unclear message")
    other = deepcopy(update)
    other["message"]["chat"]["id"] -= 1
    receive(client, headers, other, 2, "Other chat request")
    second = next(i for i in client.get("/api/enquiries").json()["items"] if i["id"] != first["id"])
    path = f"/api/assignments/{ambiguous['update_id']}"
    assert client.post(path, headers={"X-Demo-Actor": "sales"}, json={"action": "assign", "enquiry_id": second["id"]}).status_code == 422
    client.patch("/api/business-profiles/active", json={"business_profile_id": "cleaning"})
    assert client.get("/api/assignments").json()["items"] == []
    assert client.post(path, headers={"X-Demo-Actor": "sales"}, json={"action": "assign", "enquiry_id": first["id"]}).status_code == 404


def test_restart_does_not_turn_commands_or_unassigned_messages_into_enquiries(client, engine, settings, headers, update):
    receive(client, headers, update, 0, "/start")
    receive(client, headers, update, 1, "Please quote a printing job")
    receive(client, headers, update, 2, "Unclear message")
    with TestClient(create_app(settings, engine)) as reopened:
        assert len(reopened.get("/api/enquiries").json()["items"]) == 1
        assert len(reopened.get("/api/assignments").json()["items"]) == 1
