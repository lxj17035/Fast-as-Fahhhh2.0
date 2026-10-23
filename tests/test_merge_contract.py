"""Regressions for the two branches' conflicting integration contracts."""
from collections import Counter
from sqlalchemy import select
from backend.store import records


def test_each_public_operation_has_one_handler(client):
    operations = [(route.path, method) for route in client.app.routes
                  for method in getattr(route, "methods", ())]
    assert not [op for op, count in Counter(operations).items() if count > 1]


def test_automatic_and_explicit_drafting_share_saved_records(client, headers, update, engine):
    assert client.post("/api/webhooks/telegram", headers=headers, json=update).status_code == 200
    enquiry = client.get("/api/enquiries").json()["items"][0]
    automatic = client.get(f"/api/enquiries/{enquiry['id']}/quotation").json()
    explicit = client.post(f"/api/enquiries/{enquiry['id']}/draft", json={"manual": True}).json()
    assert automatic == explicit
    with engine.connect() as connection:
        quotes = connection.execute(select(records.c.body).where(records.c.kind == "quotations")).scalars().all()
    assert quotes == [automatic]
    events = client.get(f"/api/enquiries/{enquiry['id']}/activity").json()["items"]
    assert events == client.get(f"/api/enquiries/{enquiry['id']}").json()["activity"]
    assert [e["action"] for e in events].count("quotation_draft_created") == 1


def test_frontend_actor_header_is_allowed_by_cors(client):
    result = client.options("/api/quotations/example/send", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-demo-actor",
    })
    assert result.status_code == 200
    assert "x-demo-actor" in result.headers["access-control-allow-headers"].lower()
