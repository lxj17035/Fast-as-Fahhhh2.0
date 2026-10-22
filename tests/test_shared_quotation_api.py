from copy import deepcopy

from sqlalchemy import select

from app.database import telegram_updates


def receive(client, headers, update):
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    page = client.get("/api/enquiries").json()
    return next(item for item in page["items"] if item["original_text"] == update["message"]["text"])


def test_postgres_inbound_to_priced_pdf_in_one_application(client, engine, headers, update):
    enquiry = receive(client, headers, update)
    response = client.post(f'/api/enquiries/{enquiry["id"]}/draft', json={"manual": True})
    assert response.status_code == 200
    quote = response.json()
    assert quote["enquiryId"] == enquiry["id"]
    assert quote["client"]["name"] == ""  # Unknown sender is not the seeded demo client.
    path = f'/api/quotations/{quote["id"]}'
    saved = client.patch(path, json={"version": 1,
        "client": {"name": "Fictional Telegram Customer", "address": "12 Demo Road"},
        "items": [{"description": "Printed T-shirts", "quantity": 20, "unitPrice": "25.00"}],
        "missingInformation": []})
    assert saved.status_code == 200
    assert saved.json()["total"] == "500.00"
    pdf = client.get(path + "/pdf?version=2")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["x-quotation-version"] == "2"
    assert pdf.content.startswith(b"%PDF-")
    assert client.get(path + "/pdf?version=1").status_code == 409
    assert client.post(path + "/send", json={}).status_code == 403
    with engine.connect() as connection:
        row = connection.execute(select(telegram_updates)).mappings().one()
    assert row["original_text"] == update["message"]["text"]
    assert row["chat_id"] == update["message"]["chat"]["id"]
    assert client.get(f'/api/enquiries/{enquiry["id"]}').json()["original_text"] == row["original_text"]
    store = client.app.state.quotation_app.store
    assert store.get("enquiries", enquiry["id"])["chatId"] == str(row["chat_id"])


def test_repeated_shared_draft_does_not_overwrite_pm_edits(client, headers, update):
    enquiry = receive(client, headers, update)
    path = f'/api/enquiries/{enquiry["id"]}/draft'
    quote = client.post(path, json={"manual": True}).json()
    client.patch(f'/api/quotations/{quote["id"]}', json={"version": 1, "notes": "PM prepared this"})
    repeated = client.post(path, json={"manual": True}).json()
    assert repeated["version"] == 2
    assert repeated["notes"] == "PM prepared this"


def test_different_unknown_customers_get_separate_empty_client_records(client, headers, update):
    first = receive(client, headers, update)
    other = deepcopy(update)
    other["update_id"] += 1
    other["message"]["chat"]["id"] -= 1
    other["message"]["text"] = "Another fictional customer enquiry"
    second = receive(client, headers, other)
    drafts = [client.post(f'/api/enquiries/{enquiry["id"]}/draft', json={"manual": True}).json()
              for enquiry in (first, second)]
    assert drafts[0]["client"]["id"] != drafts[1]["client"]["id"]
    assert all(quote["client"]["name"] == "" for quote in drafts)


def test_shared_settings_and_demo_routes(client):
    assert client.get("/api/health").status_code == 200
    assert client.patch("/api/settings", json={"defaultValidity": "7d"}).status_code == 200
    assert client.get("/api/settings").json()["defaultValidity"] == "7d"
    assert client.patch("/api/settings", json={"defaultValidity": "bad"}).status_code == 422
    assert client.get("/api/clients/demo-client").status_code == 200
    assert client.patch("/api/clients/demo-client", json={"name": "Fictional Customer"}).status_code == 200
    demo = client.post("/api/demo/enquiries", json={"text": "Fictional sample"})
    assert demo.status_code == 201
    assert demo.json()["source"] == "demo"
    draft = client.post(f'/api/enquiries/{demo.json()["id"]}/draft', json={"manual": True})
    assert draft.status_code == 200
