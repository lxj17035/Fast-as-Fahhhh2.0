from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.database import send_attempts, save_update
from app.main import create_app
from app.telegram_client import DeliveryResult
from backend.errors import AppError
from tests.test_routing_v2 import receive
from tests.test_xinjie_integration import integrated, draft, ready, preview, deliver


def review(client, quote, role="pm", version=None):
    return client.get(f"/api/quotations/{quote['id']}/review", params={"version": version or quote["version"]},
                      headers={"X-Demo-Actor": role} if role else {})


@pytest.mark.parametrize("role", [None, "sales", "ai"])
@pytest.mark.parametrize("price_key", ["unitPrice", "unit_price"])
def test_only_manager_can_set_prices_and_api_cannot_be_spoofed(integrated, role, price_key):
    client, sender, enquiry = integrated
    quote = draft(client, enquiry)
    item = {"description": "Synthetic service", "quantity": 2, price_key: "25.00"}
    path = f"/api/quotations/{quote['id']}"
    response = client.patch(path, headers={"X-Demo-Actor": role} if role else {},
                            json={"version": 1, "items": [item]})
    assert response.status_code == (401 if role == "ai" else 403)
    assert client.get(path).json() == quote
    assert sender.calls == []
    approved = client.patch(path, headers={"X-Demo-Actor": "pm"}, json={"version": 1, "items": [item]})
    assert approved.status_code == 200
    assert approved.json()["total"] == "50.00"


def test_staff_can_prepare_details_and_keep_manager_prices_but_cannot_clear_them(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    path = f"/api/quotations/{quote['id']}"
    patch = {"version": quote["version"], "items": [
        {"item_name": "Reviewed service name", "quantity": 30, "unit": "pcs", "unit_price": "25.00"}]}
    saved = client.patch(path, headers={"X-Demo-Actor": "sales"}, json=patch)
    assert saved.status_code == 200 and saved.json()["items"][0]["unit_price"] == "25.00"
    patch["version"] = saved.json()["version"]
    patch["items"][0]["unit_price"] = None
    assert client.patch(path, headers={"X-Demo-Actor": "sales"}, json=patch).status_code == 403


def test_disabled_demo_role_cannot_change_price(integrated, engine, settings):
    client, _, enquiry = integrated
    quote = draft(client, enquiry)
    with TestClient(create_app(settings, engine)) as disabled:
        response = disabled.patch(f"/api/quotations/{quote['id']}", headers={"X-Demo-Actor": "pm"},
                                  json={"version": 1, "items": [{"description": "Item", "quantity": 1, "unitPrice": 5}]})
    assert response.status_code == 503


def test_provider_cannot_set_price_even_with_injected_invalid_authority(client):
    enquiry = client.post("/api/demo/enquiries", json={"text": "Synthetic extraction"}).json()
    quotes = client.app.state.quotation_app.quotations
    quote = quotes.create(enquiry["id"], extracted={"items": [
        {"description": "AI draft", "quantity": 2, "unitPrice": "500.00", "unit_price": "600.00"}],
        "business_profile_id": "repair", "approved": True})
    assert quote["items"][0]["unit_price"] is None and quote["total"] is None
    assert quote["business_profile_id"] == "printing" and quote["status"] == "draft"
    with pytest.raises(AppError) as error:
        quotes.update(quote["id"], {"version": 1, "items": [
            {"item_name": "AI pricing attempt", "quantity": 2, "unit_price": 10}]}, role="ai")
    assert error.value.status == 403


def test_message_arriving_during_ai_call_is_not_silently_marked_reviewed(client, engine):
    app = client.app.state.quotation_app
    assert save_update(engine, 88001, 99001, -77001, "Need 1000 printed flyers")
    [enquiry] = app.store.list("enquiries")

    class SlowExtractor:
        def extract(self, message, context):
            assert "1500" not in message
            save_update(engine, 88002, 99002, -77001, "Actually 1500 flyers")
            return {"summary": "Original 1000 flyers", "clientName": "Fictional Client",
                    "items": [{"description": "Flyers", "quantity": 1000}], "missingInformation": []}

    app.drafts.extractor = SlowExtractor()
    quote = app.drafts.create(enquiry["id"])
    assert quote["reviewedMessageIds"] == ["88001"]
    assert app.quotations.source_ids(enquiry["id"]) == ["88001", "88002"]
    assert not app.quotations.source_is_current(quote)
    priced = app.quotations.update(quote["id"], {"version": 1, "items": [
        {"description": "Flyers", "quantity": 1000, "unitPrice": "0.20"}]}, role="pm")
    with pytest.raises(AppError) as error:
        app.quotations.validate_for_send(priced["id"], priced["version"], "pm")
    assert error.value.status == 409


@pytest.mark.parametrize("role,status", [(None, 403), ("sales", 403), ("ai", 401)])
def test_final_review_requires_manager_role(integrated, role, status):
    client, _, enquiry = integrated
    assert review(client, ready(client, enquiry), role).status_code == status


def test_review_pdf_summary_and_approved_snapshot_share_one_saved_version(integrated, engine):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    client.patch("/api/settings", json={"companyName": "Changed after quotation snapshot"})
    response = review(client, quote)
    assert response.status_code == 200, response.text
    data = response.json()
    pdf = preview(client, quote).content
    assert data["quotation"] == quote
    assert data["business_profile"]["companyName"] == quote["company"]["companyName"]
    assert data["pdf"]["version"] == quote["version"]
    assert data["pdf"]["sha256"] == sha256(pdf).hexdigest()
    for expected in [quote["number"], "RM 500.00", quote["issueDate"], quote["expiryDate"], "before the expiry"]:
        assert expected in data["telegram_summary"]
    assert deliver(client, quote).status_code == 200
    with engine.connect() as connection:
        [attempt] = connection.execute(select(send_attempts)).mappings().all()
    assert attempt["summary_text"] == data["telegram_summary"]
    assert attempt["source_message_ids"] == data["source_message_ids"]
    assert attempt["pdf_sha256"] == data["pdf"]["sha256"]
    assert attempt["pdf_bytes"] == pdf


@pytest.mark.parametrize("outcome,status", [("failed", 502), ("unknown", 202)])
def test_failed_or_uncertain_delivery_is_never_marked_sent(integrated, engine, outcome, status):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    assert review(client, quote).status_code == 200
    sender.result = DeliveryResult(outcome, error_code="telegram_403" if outcome == "failed" else "telegram_timeout")
    result = deliver(client, quote)
    assert result.status_code == status
    with engine.connect() as connection:
        [attempt] = connection.execute(select(send_attempts)).mappings().all()
    assert attempt["status"] == outcome and attempt["summary_text"]
    assert client.get(f"/api/enquiries/{enquiry['id']}").json()["status"] == outcome


def test_review_rejects_stale_version_and_new_customer_facts(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    changed = client.patch(f"/api/quotations/{quote['id']}", json={"version": quote["version"], "notes": "Human edit"}).json()
    assert review(client, quote).status_code == 409
    assert review(client, changed).status_code == 200
    receive(client, headers, update, 1, "Actually please use blue")
    assert review(client, changed).status_code == 409


def test_blank_price_differs_from_explicit_zero_in_review(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    path = f"/api/quotations/{quote['id']}"
    item = {"item_name": "Complimentary sample", "quantity": 1, "unit": "pcs", "unit_price": None}
    blank = client.patch(path, headers={"X-Demo-Actor": "pm"}, json={"version": quote["version"], "items": [item]}).json()
    assert blank["total"] is None and review(client, blank).status_code == 422
    item["unit_price"] = "0.00"
    zero = client.patch(path, headers={"X-Demo-Actor": "pm"}, json={"version": blank["version"], "items": [item]}).json()
    assert zero["total"] == "0.00"
    assert "RM 0.00" in review(client, zero).json()["telegram_summary"]


def test_new_message_during_upload_keeps_approved_pdf_and_flags_fresh_review(integrated, headers, update, engine):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    sender.entered, sender.release = Event(), Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(deliver, client, quote)
        try:
            assert sender.entered.wait(timeout=10)
            receive(client, headers, update, 1, "Actually quantity should be 1500")
            assert len(client.get("/api/enquiries").json()["items"]) == 1
            assert client.get(f"/api/enquiries/{enquiry['id']}").json()["status"] == "unknown"
        finally:
            sender.release.set()
        assert job.result(timeout=15).status_code == 200
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    assert detail["status"] == "needs_review" and len(detail["messages"]) == 2
    assert preview(client, quote).content == pdf
    with engine.connect() as connection:
        [attempt] = connection.execute(select(send_attempts)).mappings().all()
    assert attempt["source_message_ids"] == [str(update["update_id"])]
    assert "RM 500.00" in attempt["summary_text"]


def test_customer_reply_to_sent_pdf_is_tied_to_its_enquiry(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    assert deliver(client, quote).status_code == 200
    receive(client, headers, update, 1, "Can you amend this?", reply=87654321)
    [item] = client.get("/api/enquiries").json()["items"]
    assert item["id"] == enquiry["id"] and item["status"] == "needs_review"
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    assert detail["messages"][-1]["assignment_history"][-1]["reply_to_message_id"] == "87654321"


def test_postgres_review_snapshot_columns_upgrade_without_changing_saved_pdf(integrated, engine, settings):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL-only legacy snapshot column upgrade")
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE send_attempts DROP COLUMN summary_text"))
        connection.execute(text("ALTER TABLE send_attempts DROP COLUMN source_message_ids"))
    for _ in range(2):
        with TestClient(create_app(settings, engine)) as reopened:
            assert preview(reopened, quote).content == pdf
            [attempt] = reopened.get(f"/api/enquiries/{enquiry['id']}").json()["delivery_attempts"]
            assert attempt["status"] == "sent" and attempt["telegram_summary"] is None
