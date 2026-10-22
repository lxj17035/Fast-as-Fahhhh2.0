"""Server configuration, loaded without exposing credentials in repr or errors."""

import os
import re
from dataclasses import dataclass, field

from app.db_url import postgres_url


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    telegram_webhook_secret: str = field(repr=False)
    telegram_bot_token: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", self.telegram_webhook_secret):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must contain 1-256 letters, digits, "
                "underscores or hyphens"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            database_url=os.environ.get("DATABASE_URL", ""),
            telegram_webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
        )
        return cls(database_url=postgres_url(settings.database_url).render_as_string(hide_password=False),
                   telegram_webhook_secret=settings.telegram_webhook_secret,
                   telegram_bot_token=settings.telegram_bot_token)
