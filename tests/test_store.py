from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import text

from app.db_url import postgres_url
from backend.errors import AppError
from backend.quotations import QuotationService
from backend.settings import SettingsService
from backend.store import Store


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_postgres_urls_preserve_credentials_and_ssl_options(prefix):
    url = postgres_url(prefix + "fictional:p%40ss@localhost:5432/demo?sslmode=require")
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss"
    assert url.query["sslmode"] == "require"


@pytest.mark.parametrize("url", ["", ":memory:", "data/local.sqlite3", "sqlite:///demo.db", "mysql://localhost/db"])
def test_runtime_rejects_non_postgres_without_exposing_credentials(url):
    with pytest.raises(ValueError) as error:
        Store(url)
    assert url not in str(error.value) if url else "required" in str(error.value)


def test_store_upsert_and_reopen(engine):
    first = Store(engine=engine)
    settings = SettingsService(first)
    settings.update_settings({"companyName": "Fictional PostgreSQL Demo"})
    first.close()
    second = Store(engine=engine)
    assert SettingsService(second).get_settings()["companyName"] == "Fictional PostgreSQL Demo"
    with second.transaction():
        second.put("checks", "unicode", {"name": "测试客户", "amount": "25.00"})
        second.put("checks", "unicode", {"name": "更新", "amount": "50.00"})
    assert second.get("checks", "unicode") == {"name": "更新", "amount": "50.00"}
    assert len(second.list("checks")) == 1
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            assert connection.execute(text("SELECT pg_typeof(body)::text FROM quotation_records LIMIT 1")).scalar() == "jsonb"


def test_nested_transaction_rollback(engine):
    store = Store(engine=engine)
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.put("checks", "outer", {"value": 1})
            with store.transaction():
                store.put("checks", "inner", {"value": 2})
                raise RuntimeError("synthetic failure")
    assert store.list("checks") == []
    with store.transaction():
        store.put("checks", "after-rollback", {"value": 3})
    assert store.get("checks", "after-rollback")["value"] == 3


def test_sent_snapshot_and_pdf_persist_in_shared_database(engine):
    from backend.pdf import PDFService
    store = Store(engine=engine)
    settings = SettingsService(store)
    quotes = QuotationService(store, settings)
    quote = quotes.create("fictional-enquiry", issue_date="2026-10-23")
    quote = quotes.update(quote["id"], {"version": 1, "items": [
        {"description": "Event shirts", "quantity": 20, "unitPrice": "25.00"}]}, role="pm")
    before = PDFService(store, quotes).get(quote["id"], 2)[0]
    quotes.begin_send(quote["id"], 2, "Fictional PM", "pm", today=date(2026, 10, 23))
    quotes.record_send_result(quote["id"], "accepted", "fictional-reference")
    settings.update_settings({"companyName": "Other Fictional Company"})
    reopened = Store(engine=engine)
    new_quotes = QuotationService(reopened, SettingsService(reopened))
    saved = new_quotes.get(quote["id"])
    assert saved["total"] == "500.00"
    assert saved["status"] == "sent"
    assert saved["company"]["companyName"] != "Other Fictional Company"
    assert PDFService(reopened, new_quotes).get(quote["id"], 2)[0] == before


def test_postgres_two_store_instances_cannot_approve_twice(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("Cross-instance serialization uses PostgreSQL advisory locks")
    # Separate engine identities avoid sharing the in-process lock, so this
    # exercises PostgreSQL advisory locking rather than only Python serialization.
    stores = [Store(engine=engine), Store(engine=engine.execution_options())]
    assert stores[0].lock is not stores[1].lock
    services = [QuotationService(store, SettingsService(store)) for store in stores]
    quote = services[0].create("fictional-race", issue_date="2026-10-23")
    quote = services[0].update(quote["id"], {"version": 1, "items": [
        {"description": "Event shirts", "quantity": 20, "unitPrice": "25.00"}]}, role="pm")
    def approve(service):
        try:
            service.begin_send(quote["id"], 2, "Fictional PM", "pm", today=date(2026, 10, 23))
            return True
        except AppError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(approve, services)) == 1
