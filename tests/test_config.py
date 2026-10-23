import pytest

from app.config import Settings


def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://fictional:password@localhost/test")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "synthetic-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-token")
    settings = Settings.from_env()
    assert settings.telegram_webhook_secret == "synthetic-secret"
    assert settings.telegram_bot_token == "synthetic-token"
    assert "password" not in repr(settings)
    assert "synthetic" not in repr(settings)


@pytest.mark.parametrize("secret", ["", "has space", "bad/token", "é", "a" * 257])
def test_invalid_secrets_are_rejected(secret):
    with pytest.raises(ValueError):
        Settings(database_url="postgresql+psycopg://localhost/test", telegram_webhook_secret=secret)


@pytest.mark.parametrize("url", ["", "not-a-url", "sqlite:///test.db", "mysql://localhost/test"])
def test_runtime_rejects_missing_or_unsupported_database(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "synthetic-secret")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_no_default_webhook_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/test")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_demo_approval_flag_survives_database_normalization(monkeypatch, enabled):
    monkeypatch.setenv("DATABASE_URL", "postgres://fictional:password@localhost/test")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "synthetic-secret")
    monkeypatch.setenv("ENABLE_DEMO_APPROVAL", enabled)
    assert Settings.from_env().enable_demo_approval is (enabled == "true")
