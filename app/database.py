"""Durable inbound messages; enquiry processing is added in Part 2."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, MetaData, Table, Text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
telegram_updates = Table(
    "telegram_updates",
    metadata,
    Column("update_id", BigInteger, primary_key=True, autoincrement=False),
    Column("message_id", BigInteger, nullable=False),
    Column("chat_id", BigInteger, nullable=False),
    Column("original_text", Text, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
)


def save_update(
    engine: Engine, update_id: int, message_id: int, chat_id: int, text: str
) -> bool:
    """Return True after commit; False only for an already-stored update ID."""
    try:
        with engine.begin() as connection:
            connection.execute(
                telegram_updates.insert().values(
                    update_id=update_id,
                    message_id=message_id,
                    chat_id=chat_id,
                    original_text=text,
                    received_at=datetime.now(timezone.utc),
                )
            )
    except IntegrityError as error:
        # The database primary key arbitrates concurrent deliveries atomically.
        if engine.dialect.name == "postgresql":
            diagnostic = getattr(error.orig, "diag", None)
            if (
                getattr(error.orig, "sqlstate", None) == "23505"
                and getattr(diagnostic, "constraint_name", None)
                == "telegram_updates_pkey"
            ):
                return False
        elif engine.dialect.name == "sqlite":
            # SQLite is only a test adapter. 1555 is SQLITE_CONSTRAINT_PRIMARYKEY.
            if getattr(error.orig, "sqlite_errorcode", None) == 1555:
                return False
        raise
    return True
