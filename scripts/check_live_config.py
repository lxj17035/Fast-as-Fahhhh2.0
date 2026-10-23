"""Report configuration readiness without printing values or contacting services."""
import json
import os
import re
from pathlib import Path

from app.db_url import postgres_url
from backend.config import load_env
from backend.runpod import configuration as runpod_configuration
from backend.telegram_delivery import TelegramDocumentSender


def configuration_status(values):
    try:
        postgres_url(values.get("DATABASE_URL", ""))
        database_ready = True
    except ValueError:
        database_ready = False
    provider = values.get("AI_PROVIDER", "openai").strip().lower()
    if provider == "runpod":
        try:
            runpod_configuration(values)
            config_ready = True
        except (ValueError, TypeError, AttributeError):
            config_ready = False
        ai_checks = {"RUNPOD_API_KEY": bool(values.get("RUNPOD_API_KEY", "").strip()),
                     "RUNPOD_CONFIG": config_ready}
    elif provider == "openai":
        ai_checks = {"OPENAI_API_KEY": bool(values.get("OPENAI_API_KEY", "").strip()),
                     "OPENAI_MODEL": bool(values.get("OPENAI_MODEL", "").strip())}
    else:
        ai_checks = {"AI_PROVIDER": False}
    checks = {
        "DATABASE_URL": database_ready,
        "ENABLE_DEMO_APPROVAL": values.get("ENABLE_DEMO_APPROVAL", "").lower() == "true",
        "TELEGRAM_BOT_TOKEN": TelegramDocumentSender(values.get("TELEGRAM_BOT_TOKEN")).configured,
        "TELEGRAM_WEBHOOK_SECRET": bool(re.fullmatch(r"[A-Za-z0-9_-]{1,256}", values.get("TELEGRAM_WEBHOOK_SECRET", ""))),
        "LIVE_TEST_CHAT_ID": bool(re.fullmatch(r"-?[1-9][0-9]*", values.get("LIVE_TEST_CHAT_ID", ""))),
    }
    checks.update(ai_checks)
    return {"readyForAI": all(ai_checks.values()),
            "aiProvider": provider if provider in {"runpod", "openai", "manual"} else "invalid",
            "readyForLiveTest": all(checks.values()), "checks": checks,
            "scope": "Configuration presence/format only; database access, API credentials and chat ownership are not verified"}


def main():
    load_env(Path(__file__).resolve().parent.parent / ".env")
    report = configuration_status(os.environ)
    print(json.dumps(report, indent=2))
    return 0 if report["readyForLiveTest"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
