"""Durable inbound messages and their enquiries in the shared database."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
enquiries = Table(
    "enquiries",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "telegram_update_id",
        BigInteger,
        ForeignKey("telegram_updates.update_id"),
        nullable=False,
        unique=True,
    ),
    Column("source", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("source = 'telegram'", name="enquiries_source_check"),
    CheckConstraint(
        "status IN ('needs_review', 'sent', 'failed', 'unknown')",
        name="enquiries_status_check",
    ),
)


def enquiry_values(update_id: int, received_at: datetime) -> dict:
    return {
        "id": str(uuid4()),
        "telegram_update_id": update_id,
        "source": "telegram",
        "status": "needs_review",
        "created_at": received_at,
    }


def backfill_enquiries(engine: Engine) -> None:
    """Link pre-Part-2 receipts once, preserving any existing enquiry state."""
    insert = (
        postgresql_insert if engine.dialect.name == "postgresql" else sqlite_insert
    )
    missing = (
        select(telegram_updates.c.update_id, telegram_updates.c.received_at)
        .outerjoin(
            enquiries,
            telegram_updates.c.update_id == enquiries.c.telegram_update_id,
        )
        .where(enquiries.c.id.is_(None))
    )
    with engine.begin() as connection:
        receipts = connection.execute(missing).all()
        for receipt in receipts:
            statement = (
                insert(enquiries)
                .values(**enquiry_values(receipt.update_id, receipt.received_at))
                .on_conflict_do_nothing(index_elements=["telegram_update_id"])
            )
            connection.execute(statement)


def save_update(
    engine: Engine, update_id: int, message_id: int, chat_id: int, text: str
) -> bool:
    """Commit receipt and enquiry together; False means an existing receipt."""
    receipt_inserted = False
    received_at = datetime.now(timezone.utc)
    try:
        with engine.begin() as connection:
            connection.execute(
                telegram_updates.insert().values(
                    update_id=update_id,
                    message_id=message_id,
                    chat_id=chat_id,
                    original_text=text,
                    received_at=received_at,
                )
            )
            receipt_inserted = True
            connection.execute(
                enquiries.insert().values(**enquiry_values(update_id, received_at))
            )
    except IntegrityError as error:
        # Enquiry constraint failures must roll back and be retried, not swallowed.
        if receipt_inserted:
            raise
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
