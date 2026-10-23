import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import Settings
from app.main import create_app


@pytest.fixture(params=["sqlite"] + (["postgresql"] if os.getenv("TEST_DATABASE_URL") else []))
def engine(request, tmp_path):
    """Use disposable local storage or a unique schema in an explicit test DB."""
    if request.param == "sqlite":
        database = create_engine(
            f"sqlite:///{tmp_path / 'receipts.db'}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        try:
            yield database
        finally:
            database.dispose()
        return

    url = os.environ["TEST_DATABASE_URL"]
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg")
    schema = "sweeway_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    database = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield database
    finally:
        database.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def settings(engine):
    return Settings(
        database_url=engine.url.render_as_string(hide_password=False),
        telegram_webhook_secret="synthetic-test-secret",
        telegram_bot_token="synthetic-test-bot-token",
    )


@pytest.fixture
def client(engine, settings):
    with TestClient(create_app(settings, engine)) as client:
        yield client


@pytest.fixture
def headers(settings):
    return {"X-Telegram-Bot-Api-Secret-Token": settings.telegram_webhook_secret}


@pytest.fixture
def update():
    return {
        "update_id": 12345,
        "message": {
            "message_id": 678,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "text": "  Fictional customer: 20 T-shirts\nPrint: café ☀  ",
        },
    }


@pytest.fixture(autouse=True)
def no_ambient_live_ai_keys(monkeypatch):
    """External calls must be explicitly mocked, even on a configured developer PC."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
