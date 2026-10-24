"""B1: synthetic profiles, pinned intake and scope across the real API/storage."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.database import enquiries, save_update
from app.main import create_app
from backend.errors import AppError
from backend.server import Application
from backend.settings import SettingsService, SETTINGS, DEMO_CLIENT
from backend.store import Store, records
from tests.test_xinjie_integration import integrated, ready, preview, deliver


def switch(client, identity):
    result = client.patch("/api/business-profiles/active", json={"business_profile_id": identity})
    assert result.status_code == 200, result.text
    assert result.json() == {"business_profile_id": identity}


@pytest.mark.parametrize("identity", ["printing", "cleaning", "repair"])
def test_profile_settings_and_clients_remain_separate(client, identity):
    profiles = client.get("/api/business-profiles").json()
    assert profiles["active_business_profile_id"] == "printing"
    assert {p["id"] for p in profiles["items"]} == {"printing", "cleaning", "repair"}
    assert all(p["currency"] == "MYR" for p in profiles["items"])
    switch(client, identity)
    response = client.patch("/api/settings", json={"companyName": "Changed fictional " + identity,
                                                  "defaultValidity": "14d"})
    assert response.status_code == 200
    assert response.json()["business_profile_id"] == identity
    client_id = SettingsService.demo_client_id(identity)
    assert client.patch(f"/api/clients/{client_id}", json={"name": "Fictional " + identity}).status_code == 200
    for other in {"printing", "cleaning", "repair"} - {identity}:
        switch(client, other)
        assert client.get("/api/settings").json()["defaultValidity"] == "1m"
        assert client.get(f"/api/clients/{client_id}").status_code == 404
        assert client.patch(f"/api/clients/{client_id}", json={"name": "Wrong business"}).status_code == 404
    switch(client, identity)
    assert client.get("/api/settings").json()["companyName"] == "Changed fictional " + identity
    assert client.get(f"/api/clients/{client_id}").json()["name"] == "Fictional " + identity


@pytest.mark.parametrize("patch", [{}, {"business_profile_id": "unknown"},
                                     {"business_profile_id": None}, {"business_profile_id": []},
                                     {"business_profile_id": "cleaning", "approved": True}])
def test_invalid_selection_is_atomic(client, patch):
    assert client.patch("/api/business-profiles/active", json=patch).status_code == 422
    assert client.get("/api/settings").json()["business_profile_id"] == "printing"


@pytest.mark.parametrize("patch", [{"id": "repair"}, {"industry": "Other"},
                                     {"companyName": "Changed", "defaultValidity": "invalid"}])
def test_profile_update_reuses_validation_without_changing_identity(client, patch):
    path = "/api/business-profiles/cleaning"
    before = client.get(path).json()
    assert client.patch(path, json=patch).status_code == 422
    assert client.get(path).json() == before


def test_targeted_settings_update_does_not_select_that_profile(client):
    response = client.patch("/api/business-profiles/repair", json={"companyAddress": "99 Fictional Repair Road"})
    assert response.status_code == 200
    assert client.get("/api/business-profiles/repair").json()["companyAddress"] == "99 Fictional Repair Road"
    assert client.get("/api/settings").json()["business_profile_id"] == "printing"


def test_intake_pin_survives_switch_duplicate_and_restart(client, engine, settings, headers, update):
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    [original] = client.get("/api/enquiries").json()["items"]
    assert original["business_profile_id"] == "printing"
    switch(client, "cleaning")
    assert client.get("/api/enquiries").json()["items"] == []
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).json() == {"status": "duplicate"}
    assert client.get(f"/api/enquiries/{original['id']}").status_code == 404
    other = deepcopy(update)
    other["update_id"] += 1
    other["message"]["message_id"] += 1
    assert client.post("/api/webhooks/telegram", headers=headers, json=other).status_code == 200
    [cleaning] = client.get("/api/enquiries").json()["items"]
    assert cleaning["business_profile_id"] == "cleaning"
    with TestClient(create_app(settings, engine)) as reopened:
        assert reopened.get("/api/business-profiles").json()["active_business_profile_id"] == "cleaning"
        assert reopened.get("/api/enquiries").json()["items"] == [cleaning]
        switch(reopened, "printing")
        assert reopened.get("/api/enquiries").json()["items"] == [original]
    with engine.connect() as connection:
        rows = connection.execute(select(enquiries)).mappings().all()
    assert {r["telegram_update_id"]: r["business_profile_id"] for r in rows} == {
        update["update_id"]: "printing", other["update_id"]: "cleaning",
    }


def test_demo_intake_uses_selected_profile_and_rejects_cross_profile_client(client):
    switch(client, "repair")
    assert client.post("/api/demo/enquiries", json={"text": "Synthetic repair", "clientId": "demo-client"}).status_code == 404
    assert client.app.state.quotation_app.store.list("enquiries") == []
    response = client.post("/api/demo/enquiries", json={"text": "Synthetic repair"})
    assert response.status_code == 201
    enquiry = response.json()
    assert enquiry["business_profile_id"] == "repair"
    assert enquiry["clientId"] == "demo-client-repair"
    quote = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True}).json()
    assert quote["business_profile_id"] == quote["client"]["business_profile_id"] == "repair"
    assert "Repair" in quote["company"]["companyName"]
    assert client.post("/api/demo/enquiries", json={"text": "Synthetic", "business_profile_id": "printing"}).status_code == 422


def test_delayed_draft_uses_pinned_company_and_ignores_provider_identity(client, engine):
    app = client.app.state.quotation_app
    assert save_update(engine, 80001, 90001, -70001, "Synthetic repair request")
    [enquiry] = app.store.list("enquiries")
    observed = []

    class Extractor:
        def extract(self, message, context):
            observed.append(context)
            return {"summary": message, "items": [], "missingInformation": [],
                    "business_profile_id": "repair"}

    app.drafts.extractor = Extractor()
    switch(client, "cleaning")
    app.settings.update_settings({"companyName": "Wrong company for old enquiry"})
    quote = app.drafts.create(enquiry["id"])
    assert observed[0]["company"]["business_profile_id"] == "printing"
    assert observed[0]["client"]["business_profile_id"] == "printing"
    assert quote["business_profile_id"] == "printing"
    assert quote["company"]["companyName"] != "Wrong company for old enquiry"


def test_existing_pins_and_client_associations_cannot_be_reassigned(client, engine, headers, update):
    client.post("/api/webhooks/telegram", headers=headers, json=update)
    app = client.app.state.quotation_app
    [enquiry] = app.store.list("enquiries")
    quote = app.drafts.create(enquiry["id"], manual=True)
    for kind, key in [("enquiries", enquiry["id"]), ("quotations", quote["id"]),
                      ("clients", quote["client"]["id"])]:
        before = app.store.get(kind, key)
        with pytest.raises(AppError) as error:
            with app.store.transaction():
                app.store.put(kind, key, {**before, "business_profile_id": "cleaning"})
        assert error.value.status == 409
        assert app.store.get(kind, key) == before
    with pytest.raises(AppError):
        with app.store.transaction():
            app.store.put("enquiries", enquiry["id"], {**enquiry, "clientId": "demo-client-repair"})
    assert app.store.get("enquiries", enquiry["id"])["clientId"] == quote["client"]["id"]


def test_other_profile_cannot_read_edit_preview_draft_or_send(integrated, engine):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    assert preview(client, quote).status_code == 200
    switch(client, "cleaning")
    qpath = f"/api/quotations/{quote['id']}"
    epath = f"/api/enquiries/{enquiry['id']}"
    for path in [epath, epath + "/quotation", epath + "/activity", qpath,
                 qpath + "/activity", qpath + f"/pdf?version={quote['version']}"]:
        assert client.get(path).status_code == 404, path
    assert client.patch(qpath, json={"version": quote["version"], "notes": "Wrong scope"}).status_code == 404
    assert client.post(epath + "/draft", json={"manual": True}).status_code == 404
    assert deliver(client, quote).status_code == 404
    assert sender.calls == []
    switch(client, "printing")
    assert client.get(qpath).json() == quote
    assert client.get(epath).json()["delivery_attempts"] == []
    assert deliver(client, quote).status_code == 200


def test_sent_pdf_and_metadata_survive_profile_edits_and_switch(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    original_pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    qpath = f"/api/quotations/{quote['id']}"
    sent = client.get(qpath).json()
    assert client.patch("/api/business-profiles/printing", json={"companyName": "New fictional company"}).status_code == 200
    switch(client, "repair")
    assert deliver(client, quote).status_code == 404
    switch(client, "printing")
    assert client.get(qpath).json() == sent
    assert preview(client, quote).content == original_pdf


def test_existing_settings_clients_and_sent_records_are_not_rewritten(engine):
    store = Store(engine=engine)
    old_settings = {**SETTINGS, "companyName": "Existing fictional business", "defaultValidity": "7d"}
    legacy_sent = {"id": "legacy-sent", "status": "sent", "company": old_settings}
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(records.insert(), [
            {"kind": "settings", "id": "business", "body": old_settings, "created_at": now},
            {"kind": "clients", "id": "demo-client", "body": DEMO_CLIENT, "created_at": now},
            {"kind": "quotations", "id": "legacy-sent", "body": legacy_sent, "created_at": now},
        ])
    for _ in range(2):
        settings = SettingsService(store)
        assert settings.get_settings()["companyName"] == old_settings["companyName"]
        assert settings.get_settings()["defaultValidity"] == "7d"
        settings.select_profile({"business_profile_id": "repair"})
        SettingsService(store)
        assert settings.active_profile_id() == "repair"
        settings.select_profile({"business_profile_id": "printing"})
    with engine.connect() as connection:
        assert connection.execute(select(records.c.body).where(
            records.c.kind == "quotations", records.c.id == "legacy-sent")).scalar_one() == legacy_sent


def test_concurrent_profile_switch_and_receipt_keep_consistent_scope(client, engine):
    app = client.app.state.quotation_app

    def receive(index):
        if index % 2:
            app.settings.select_profile({"business_profile_id": "repair" if index % 3 else "cleaning"})
        save_update(engine, 81000 + index, 91000 + index, -71000, "New quotation: Synthetic concurrent enquiry")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(receive, range(8)))
    for enquiry in app.store.list("enquiries"):
        quote = app.drafts.create(enquiry["id"], manual=True)
        identity = enquiry["business_profile_id"]
        assert quote["business_profile_id"] == quote["company"]["business_profile_id"] == identity
        assert quote["client"]["business_profile_id"] == identity


def test_postgres_legacy_enquiry_column_upgrade_preserves_sent_history(integrated, engine, settings):
    if engine.dialect.name != "postgresql":
        pytest.skip("Runtime schema upgrade is PostgreSQL-only")
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    history = client.get(f"/api/enquiries/{enquiry['id']}").json()["activity"]
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE enquiries DROP COLUMN business_profile_id"))
    for _ in range(2):
        with TestClient(create_app(settings, engine)) as reopened:
            detail = reopened.get(f"/api/enquiries/{enquiry['id']}").json()
            assert detail["business_profile_id"] == "printing"
            assert detail["status"] == "sent"
            assert detail["activity"] == history
            assert preview(reopened, quote).content == pdf


def test_standalone_application_obeys_the_same_profile_contract(engine):
    app = Application(Store(engine=engine))
    assert app.route("PATCH", "/api/business-profiles/active", {"business_profile_id": "repair"}, {})[0] == 200
    _, enquiry = app.route("POST", "/api/demo/enquiries", {"text": "Synthetic repair"}, {})
    assert enquiry["business_profile_id"] == "repair"
    app.route("PATCH", "/api/business-profiles/active", {"business_profile_id": "cleaning"}, {})
    with pytest.raises(AppError) as error:
        app.route("GET", f"/api/enquiries/{enquiry['id']}", {}, {})
    assert error.value.status == 404
