"""Durable inbound messages and their enquiries in the shared database."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
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
    Column("business_profile_id", String(40), nullable=False, server_default="printing"),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("source = 'telegram'", name="enquiries_source_check"),
    CheckConstraint(
        "status IN ('needs_review', 'sent', 'failed', 'unknown')",
        name="enquiries_status_check",
    ),
)
message_links = Table(
    "message_links", metadata,
    Column("update_id", BigInteger, ForeignKey("telegram_updates.update_id"), primary_key=True),
    Column("business_profile_id", String(40), nullable=False),
    Column("enquiry_id", String(36), ForeignKey("enquiries.id")),
    Column("status", String(20), nullable=False),
    Column("assigned_by", String(20), nullable=False),
    Column("history", JSON, nullable=False),
    CheckConstraint("status IN ('assigned', 'needs_assignment', 'command', 'unrelated')",
                    name="message_links_status_check"),
)
outgoing_messages = Table(
    "outgoing_messages", metadata,
    Column("id", String(36), primary_key=True),
    Column("enquiry_id", String(36), ForeignKey("enquiries.id"), nullable=False),
    Column("business_profile_id", String(40), nullable=False),
    Column("request_id", String(36), nullable=False),
    Column("actor", String(20), nullable=False),
    Column("text", Text, nullable=False),
    Column("status", String(20), nullable=False),
    Column("provider_message_id", String(80)),
    Column("safe_error_code", String(80)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("business_profile_id", "request_id", name="outgoing_request_unique"),
    CheckConstraint("status IN ('pending', 'sent', 'failed', 'unknown')", name="outgoing_status_check"),
)
send_attempts = Table(
    "send_attempts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("quotation_id", String(36), nullable=False),
    Column("retry_of_attempt_id", String(36), ForeignKey("send_attempts.id")),
    Column("enquiry_id", String(36), ForeignKey("enquiries.id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("actor_id", String(40), nullable=False),
    Column("role", String(10), nullable=False),
    Column("approved_at", DateTime(timezone=True), nullable=False),
    Column("pdf_sha256", String(64), nullable=False),
    Column("pdf_bytes", LargeBinary, nullable=False),
    Column("summary_text", Text),
    Column("pdf_status", String(20)),
    Column("summary_status", String(20)),
    Column("summary_provider_message_id", String(80)),
    Column("source_message_ids", JSON),
    Column("status", String(20), nullable=False),
    Column("provider_message_id", String(80)),
    Column("safe_error_code", String(80)),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("role = 'pm'", name="send_attempts_role_check"),
    CheckConstraint(
        "status IN ('pending', 'sent', 'failed', 'unknown')",
        name="send_attempts_status_check",
    ),
)
# Each explicit approval is durable. A failure may have one approved successor;
# duplicate initial requests and replayed retry approvals cannot create siblings.
Index("send_attempts_initial_unique", send_attempts.c.quotation_id, unique=True,
      postgresql_where=send_attempts.c.retry_of_attempt_id.is_(None),
      sqlite_where=send_attempts.c.retry_of_attempt_id.is_(None))
Index("send_attempts_retry_unique", send_attempts.c.retry_of_attempt_id, unique=True)

activities = Table(
    "activities",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("enquiry_id", String(36), ForeignKey("enquiries.id"), nullable=False),
    Column("quotation_id", String(36)),
    Column("version", Integer),
    Column("attempt_id", String(36), ForeignKey("send_attempts.id")),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("actor_id", String(80)),
    Column("role", String(20)),
    Column("actor_origin", String(20), nullable=False),
    Column("action", String(40), nullable=False),
    Column("result", String(40), nullable=False),
    Column("provider_reference", String(100)),
    Column("safe_error_code", String(80)),
    CheckConstraint(
        "actor_origin IN ('system', 'simulated', 'unknown')",
        name="activities_actor_origin_check",
    ),
    Index("activities_enquiry_timestamp", "enquiry_id", "timestamp", "id"),
)


def enquiry_values(update_id: int, received_at: datetime, business_profile_id="printing") -> dict:
    return {
        "id": str(uuid4()),
        "telegram_update_id": update_id,
        "source": "telegram",
        "business_profile_id": business_profile_id,
        "status": "needs_review",
        "created_at": received_at,
    }


def backfill_enquiries(engine: Engine) -> None:
    """Link old receipts without inventing historical activity or changing state."""
    insert = (
        postgresql_insert if engine.dialect.name == "postgresql" else sqlite_insert
    )
    missing = (
        select(telegram_updates.c.update_id, telegram_updates.c.received_at)
        .outerjoin(
            enquiries,
            telegram_updates.c.update_id == enquiries.c.telegram_update_id,
        )
        .outerjoin(message_links, message_links.c.update_id == telegram_updates.c.update_id)
        .where(enquiries.c.id.is_(None), message_links.c.update_id.is_(None))
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
        # Existing enquiries keep their original association. New V2 commands
        # and unassigned messages already have links and are never backfilled.
        for row in connection.execute(select(enquiries)).mappings():
            connection.execute(insert(message_links).values(
                update_id=row["telegram_update_id"], business_profile_id=row["business_profile_id"],
                enquiry_id=row["id"], status="assigned", assigned_by="legacy", history=[],
            ).on_conflict_do_nothing(index_elements=[message_links.c.update_id]))


def save_update(
    engine: Engine, update_id: int, message_id: int, chat_id: int, text: str,
    reply_to_message_id: int | None = None,
) -> bool:
    """Commit receipt, enquiry and real events; False means an existing receipt."""
    from app.routing import route_receipt
    from app.xinjie_store import Store, integration_transaction
    from backend.settings import SettingsService

    receipt_inserted = False
    received_at = datetime.now(timezone.utc)
    try:
        with integration_transaction(engine) as connection:
            settings = SettingsService(Store(engine, connection))
            identity = settings.active_profile_id()
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
            route_receipt(connection, update_id, message_id, chat_id, text,
                          received_at, identity, reply_to_message_id)
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
