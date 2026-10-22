import json

from scripts.check_live_config import configuration_status


def test_empty_configuration_is_not_ready():
    report = configuration_status({})
    assert report["readyForLiveTest"] is False
    assert not any(report["checks"].values())


def test_valid_looking_configuration_reports_no_private_values():
    values = {"DATABASE_URL": "postgresql://fictional:private-password@localhost/test",
              "TELEGRAM_BOT_TOKEN": "123:fake-private-token", "TELEGRAM_WEBHOOK_SECRET": "fake-private-secret",
              "OPENAI_API_KEY": "fake-private-key", "OPENAI_MODEL": "test-model", "LIVE_TEST_CHAT_ID": "-100123"}
    report = configuration_status(values)
    assert report["readyForLiveTest"] is True
    output = json.dumps(report)
    for value in values.values():
        assert value not in output
    assert "not verified" in report["scope"]


def test_invalid_database_token_webhook_and_zero_chat_are_not_ready():
    report = configuration_status({"DATABASE_URL": "sqlite:///not-runtime.db",
        "TELEGRAM_BOT_TOKEN": "placeholder", "TELEGRAM_WEBHOOK_SECRET": "bad secret", "LIVE_TEST_CHAT_ID": "0"})
    assert report["readyForLiveTest"] is False
    for key in ("DATABASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "LIVE_TEST_CHAT_ID"):
        assert report["checks"][key] is False
