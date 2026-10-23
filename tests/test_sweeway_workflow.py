"""Sweeway lifecycle QA: real service adapters, mocked external transports only."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
from email import policy
from email.parser import BytesParser
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.telegram_client import TelegramSender
from backend.drafting import OpenAIExtractor


EXTRACTION = {
    "summary": "Fictional customer requests 20 printed shirts",
    "clientName": None,
    "clientAddress": None,
    "items": [{"description": "Printed shirts", "quantity": 20}],
    "missingInformation": [],
}


def completed_response(value):
    return {"status": "completed", "output": [{
        "type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]
    }]}


@pytest.fixture
def workflow(engine, settings, update, headers, request):
    state = {"mode": getattr(request, "param", "success"), "ai_requests": [], "telegram_requests": []}

    def extract_transport(payload):
        state["ai_requests"].append(payload)
        if state["mode"] == "timeout":
            raise TimeoutError("synthetic-private-provider-error")
        if state["mode"] == "refusal":
            return {"status": "completed", "output": [{
                "type": "message", "content": [{"type": "refusal", "refusal": "synthetic refusal"}]
            }]}
        extracted = deepcopy(EXTRACTION)
        if state["mode"] == "price":
            extracted["items"][0]["unitPrice"] = 1
        if state["mode"] == "recipient":
            extracted["recipient"] = "999999999"
        return completed_response(extracted)

    def telegram_transport(request):
        raw = request.read()
        mime = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {request.headers['content-type']}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + raw
        )
        parts = {part.get_param("name", header="content-disposition"): part
                 for part in mime.iter_parts()}
        chat_id = parts["chat_id"].get_payload(decode=True).decode()
        pdf = parts["document"].get_payload(decode=True)
        assert chat_id == str(update["message"]["chat"]["id"])
        assert parts["document"].get_content_type() == "application/pdf"
        assert parts["document"].get_filename() == "quotation.pdf"
        assert pdf.startswith(b"%PDF-")
        assert request.method == "POST"
        assert request.url.host == "api.telegram.org"
        assert request.url.path.endswith("/sendDocument")
        state["telegram_requests"].append({"chat_id": chat_id, "pdf": pdf})
        return httpx.Response(200, json={
            "ok": True, "result": {"message_id": 424242, "chat": {"id": int(chat_id)}}
        })

    app = create_app(
        replace(settings, enable_demo_approval=True), engine,
        ai_extractor=OpenAIExtractor("synthetic", "testmodel", transport=extract_transport),
        telegram_sender=TelegramSender("synthetic-telegram-token", httpx.MockTransport(telegram_transport)),
    )
    with TestClient(app) as client:
        response = client.post("/api/webhooks/telegram", headers=headers, json=update)
        assert response.status_code == 200
        state["client"] = client
        state["enquiry"] = client.get("/api/enquiries").json()["items"][0]
        yield state


def send(client, quote, actor="pm"):
    return client.post(f"/api/quotations/{quote['id']}/send",
                       headers={"X-Demo-Actor": actor},
                       json={"expected_version": quote["version"], "approved": True})


def detail(workflow):
    return workflow["client"].get(f"/api/enquiries/{workflow['enquiry']['id']}").json()


def test_sweeway_ai_boundary_to_actual_telegram_transport(workflow, update, headers):
    client, enquiry = workflow["client"], workflow["enquiry"]
    response = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": False})
    assert response.status_code == 200
    quote = response.json()
    assert quote["draftMode"] == "ai"
    assert quote["items"][0]["quantity"] == "20"
    assert quote["items"][0]["unitPrice"] is None
    assert quote["total"] is None
    [extraction_request] = workflow["ai_requests"]
    source = json.loads(extraction_request["input"])
    assert source["message"] == update["message"]["text"].strip()
    assert source["businessContext"]["company"] == client.get("/api/settings").json()
    assert source["businessContext"]["client"] == client.get(f"/api/clients/{quote['client']['id']}").json()
    assert extraction_request["store"] is False
    assert detail(workflow)["messages"][0]["text"] == update["message"]["text"]
    assert send(client, quote, actor="sales").status_code == 403
    assert workflow["telegram_requests"] == []
    edited = client.patch(f"/api/quotations/{quote['id']}",
                          headers={"X-Demo-Actor": "pm"}, json={
                              "version": 1, "client": {"name": "Fictional Customer"}, "items": [{"description": "Printed shirts",
                              "quantity": "20", "unitPrice": "25.00"}], "missingInformation": [],
                          })
    assert edited.status_code == 200
    quote = edited.json()
    assert quote["version"] == 2 and quote["total"] == "500.00"
    pdf = client.get(f"/api/quotations/{quote['id']}/pdf", params={"version": 2})
    assert pdf.status_code == 200
    delivered = send(client, quote)
    assert delivered.status_code == 200
    assert workflow["telegram_requests"] == [{
        "chat_id": str(update["message"]["chat"]["id"]), "pdf": pdf.content,
    }]
    final_detail = detail(workflow)
    assert final_detail["status"] == "sent"
    [attempt] = final_detail["delivery_attempts"]
    assert attempt["provider_message_id"] == "424242"
    assert attempt["status"] == "sent"
    assert attempt["attempt_id"] == delivered.json()["attempt_id"]
    events = final_detail["activity"]
    assert Counter(event["action"] for event in events) == Counter({
        "telegram_received": 1, "enquiry_created": 1, "quotation_draft_created": 1,
        "quotation_updated": 1, "pm_approved": 1, "pdf_send_attempted": 1,
        "pdf_send_succeeded": 1,
    })
    by_action = {event["action"]: event for event in events}
    for action in ("quotation_updated", "pm_approved", "pdf_send_attempted", "pdf_send_succeeded"):
        assert by_action[action]["actor_id"] == "pm"
        assert by_action[action]["role"] == "pm"
        assert by_action[action]["actor_origin"] == "simulated"
    assert by_action["quotation_draft_created"]["actor_origin"] == "system"
    assert by_action["pdf_send_succeeded"]["provider_reference"] == "424242"
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).json()["status"] == "duplicate"
    assert send(client, quote).status_code == 409
    assert len(workflow["telegram_requests"]) == 1
    assert detail(workflow)["activity"] == events


@pytest.mark.parametrize("workflow", ["timeout", "refusal", "price", "recipient"], indirect=True)
def test_failed_or_out_of_contract_extraction_preserves_manual_enquiry(workflow, update):
    client, enquiry = workflow["client"], workflow["enquiry"]
    response = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": False})
    assert response.status_code == 200
    quote = response.json()
    assert quote["draftMode"] == "manual"
    assert quote["draftError"]
    assert "synthetic-private-provider-error" not in quote["draftError"]
    assert quote["items"] == []
    assert quote["missingInformation"]
    assert workflow["telegram_requests"] == []
    assert len(workflow["ai_requests"]) == 1
    saved = detail(workflow)
    assert saved["status"] == "needs_review"
    assert saved["original_text"] == update["message"]["text"]
    assert saved["messages"][0]["chat_id"] == str(update["message"]["chat"]["id"])
    assert saved["delivery_attempts"] == []
    assert Counter(item["action"] for item in saved["activity"]) == Counter({
        "telegram_received": 1, "enquiry_created": 1, "quotation_draft_created": 1,
    })
    manual = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True})
    assert manual.status_code == 200 and manual.json()["id"] == quote["id"]
    assert len(workflow["ai_requests"]) == 1
    corrected = client.patch(f"/api/quotations/{quote['id']}", json={
        "version": 1, "client": {"name": "Fictional Customer"}, "items": [{"description": "Manually reviewed shirts",
        "quantity": "20", "unitPrice": "25.00"}], "missingInformation": [],
    })
    assert corrected.status_code == 200
    assert corrected.json()["total"] == "500.00"
    assert workflow["telegram_requests"] == []
