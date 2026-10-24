from copy import deepcopy
from dataclasses import replace
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import create_app
from backend.errors import AppError
from backend.quotation_changes import QuotationChanges
from tests.test_routing_v2 import receive
from tests.test_xinjie_integration import integrated, ready, preview, deliver


@pytest.mark.parametrize("profile,unit,name,notes", [
    ("printing", "pcs", "Event flyers", "A5, full colour, 150gsm"),
    ("cleaning", "visit", "Office cleaning", "800 sq ft; windows included"),
    ("repair", "hour", "Laptop diagnosis", "Fictional device; screen fault"),
])
def test_generic_items_exact_totals_and_pdf_notes(client, profile, unit, name, notes):
    client.patch("/api/business-profiles/active", json={"business_profile_id": profile})
    enquiry = client.post("/api/demo/enquiries", json={"text": "Synthetic " + name}).json()
    quote = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True}).json()
    saved = client.patch(f"/api/quotations/{quote['id']}", json={"version": 1, "items": [
        {"item_name": name, "quantity": "2.5", "unit": unit, "unit_price": "10.00", "notes": notes}],
        "missingInformation": []})
    assert saved.status_code == 200, saved.text
    value = saved.json()
    item = value["items"][0]
    assert item["item_name"] == item["description"] == name
    assert item["unit_price"] == item["unitPrice"] == "10.00"
    assert item["amount"] == item["lineTotal"] == value["total"] == "25.00"
    pdf = client.get(f"/api/quotations/{quote['id']}/pdf?version=2")
    content = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert name in content and notes in content and f"Unit: {unit}" in content


def test_new_messages_block_stale_pdf_and_send_until_explicit_review(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    assert preview(client, quote).status_code == 200
    receive(client, headers, update, 1, "Actually quantity 1500")
    assert preview(client, quote).status_code == 409
    assert deliver(client, quote).status_code == 409
    path = f"/api/quotations/{quote['id']}"
    assert client.patch(path, headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "reviewedMessageIds": [str(update["update_id"])]}).status_code == 409
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    ids = [m["update_id"] for m in detail["messages"]]
    response = client.patch(path, headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "reviewedMessageIds": ids,
        "items": [{"item_name": "Printed shirts", "quantity": 1500, "unit": "pcs", "unit_price": "25.00"}]})
    assert response.status_code == 200
    assert response.json()["version"] == quote["version"] + 1
    assert preview(client, response.json()).status_code == 200


def test_unassigned_message_requires_resolution_before_formal_preview_or_send(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    assert preview(client, quote).status_code == 200
    pending = receive(client, headers, update, 1, "What about that other thing?")
    assert preview(client, quote).status_code == 409
    assert deliver(client, quote).status_code == 409
    resolved = client.post(f"/api/assignments/{pending['update_id']}", headers={"X-Demo-Actor": "sales"},
                           json={"action": "unrelated"})
    assert resolved.status_code == 200
    assert preview(client, quote).status_code == 200


def test_selected_suggestions_require_human_apply_preserve_other_fields_and_audit(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    service = QuotationChanges(client.app.state.quotation_app.quotations)
    proposals = service.suggest(quote["id"], [
        {"type": "UPDATE_ITEM", "index": 0, "data": {"quantity": 30}},
        {"type": "UPDATE_FIELD", "field": "notes", "value": "AI suggested note"},
        {"type": "ADD_ITEM", "data": {"item_name": "Packaging", "quantity": 1, "unit": "job"}},
    ])
    path = f"/api/quotations/{quote['id']}"
    assert client.get(path).json() == quote
    selected = proposals["changes"][0]["id"]
    patch = {"version": quote["version"], "suggestion_set_id": proposals["id"], "selected": [selected],
             "edits": {selected: {"type": "UPDATE_ITEM", "index": 0, "data": {"quantity": 35}}}}
    assert client.post(path + "/apply-changes", json=patch).status_code == 403
    response = client.post(path + "/apply-changes", headers={"X-Demo-Actor": "sales"}, json=patch)
    assert response.status_code == 200
    saved = response.json()
    assert saved["items"][0]["quantity"] == "35"
    assert saved["items"][0]["unitPrice"] == quote["items"][0]["unitPrice"]
    assert saved["notes"] == quote["notes"] and len(saved["items"]) == 1
    applied = client.get(path + "/suggestions").json()["items"][0]
    assert applied["applied"] and applied["appliedBy"] == "sales"
    assert applied["appliedChanges"][0]["data"]["quantity"] == 35
    assert client.post(path + "/apply-changes", headers={"X-Demo-Actor": "sales"}, json=patch).status_code == 409


def test_stale_invalid_or_price_suggestions_cannot_overwrite_staff_edits(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    service = QuotationChanges(client.app.state.quotation_app.quotations)
    for change in [{"type": "UPDATE_ITEM", "index": 0, "data": {"unit_price": "0"}},
                   {"type": "UPDATE_FIELD", "field": "business_profile_id", "value": "repair"},
                   {"type": "SEND", "value": "forbidden"}, {"type": []},
                   {"type": "UPDATE_FIELD", "field": [], "value": "forbidden"}]:
        with pytest.raises(AppError):
            service.suggest(quote["id"], [change])
    proposals = service.suggest(quote["id"], [{"type": "UPDATE_FIELD", "field": "notes", "value": "Old suggestion"}])
    path = f"/api/quotations/{quote['id']}"
    saved = client.patch(path, json={"version": quote["version"], "notes": "Staff edited"}).json()
    response = client.post(path + "/apply-changes", headers={"X-Demo-Actor": "sales"}, json={
        "version": saved["version"], "suggestion_set_id": proposals["id"],
        "selected": [proposals["changes"][0]["id"]]})
    assert response.status_code == 409
    assert client.get(path).json() == saved


@pytest.mark.parametrize("item", [
    {"item_name": "Item", "description": None},
    {"item_name": "Item", "unit": ""},
    {"item_name": "Item", "unit_price": "10.00", "unitPrice": "20.00"},
    {"item_name": "Item", "amount": "1.00"},
])
def test_invalid_generic_items_are_validation_errors_and_do_not_save(client, item):
    enquiry = client.post("/api/demo/enquiries", json={"text": "Synthetic draft"}).json()
    quote = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True}).json()
    path = f"/api/quotations/{quote['id']}"
    response = client.patch(path, json={"version": 1, "items": [item]})
    assert response.status_code == 422
    assert client.get(path).json() == quote


def test_invalid_selected_change_rolls_back_all_changes(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    service = QuotationChanges(client.app.state.quotation_app.quotations)
    proposal = service.suggest(quote["id"], [
        {"type": "UPDATE_FIELD", "field": "notes", "value": "Should roll back"},
        {"type": "UPDATE_ITEM", "index": 99, "data": {"quantity": 5}}])
    response = client.post(f"/api/quotations/{quote['id']}/apply-changes", headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "suggestion_set_id": proposal["id"],
        "selected": [c["id"] for c in proposal["changes"]]})
    assert response.status_code == 409
    assert client.get(f"/api/quotations/{quote['id']}").json() == quote


def test_revision_keeps_sent_pdf_and_creates_unpriced_reviewable_draft(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    original = client.get(f"/api/quotations/{quote['id']}").json()
    receive(client, headers, update, 1, "Amend quantity to 1500; combine with original order")
    path = f"/api/quotations/{quote['id']}/fork"
    revision = client.post(path, headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "relationship": "revision"})
    assert revision.status_code == 200, revision.text
    value = revision.json()
    assert value["id"] != quote["id"] and value["enquiryId"] == enquiry["id"]
    assert value["parentQuotationId"] == quote["id"] and value["relationship"] == "revision"
    assert value["items"][0]["unit_price"] is None and value["total"] is None
    assert client.get(f"/api/quotations/{quote['id']}").json() == original
    assert preview(client, quote).content == pdf
    assert client.get(f"/api/enquiries/{enquiry['id']}/quotation").json()["id"] == value["id"]
    assert deliver(client, value).status_code != 200
    assert len(client.get(f"/api/enquiries/{enquiry['id']}/quotations").json()["items"]) == 2


def test_additional_requires_separate_enquiry_and_keeps_it_independent(integrated, headers, update):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    assert deliver(client, quote).status_code == 200
    path = f"/api/quotations/{quote['id']}/fork"
    receive(client, headers, update, 1, "New quotation for a separate order of signs")
    other = next(e for e in client.get("/api/enquiries").json()["items"] if e["id"] != enquiry["id"])
    response = client.post(path, headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "relationship": "additional", "enquiry_id": other["id"]})
    assert response.status_code == 200
    assert response.json()["enquiryId"] == other["id"]
    assert response.json()["parentQuotationId"] == quote["id"]
    assert response.json()["status"] == "draft" and response.json()["total"] is None
    assert client.post(path, headers={"X-Demo-Actor": "sales"}, json={
        "version": quote["version"], "relationship": "unclear"}).status_code == 422


def test_incomplete_pdf_is_draft_and_cannot_be_formally_sent(client):
    enquiry = client.post("/api/demo/enquiries", json={"text": "Unknown requirements"}).json()
    quote = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True}).json()
    content = client.get(f"/api/quotations/{quote['id']}/pdf?version=1").content
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(content)).pages)
    assert "DRAFT QUOTATION" in text and "INCOMPLETE DRAFT" in text
    with pytest.raises(AppError):
        client.app.state.quotation_app.quotations.validate_for_send(quote["id"], 1, "pm")
