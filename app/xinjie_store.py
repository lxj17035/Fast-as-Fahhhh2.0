"""Adapt Xinjie's record API to the application's existing SQLAlchemy database."""

from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from app.activity import record_activity
from backend.store import Store as SharedStore, WRITE_LOCK, engine_lock

_ADVISORY_LOCK = WRITE_LOCK


def lock_integration(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK}
        )


@contextmanager
def integration_transaction(engine: Engine):
    """Serialize prototype version checks, edits, previews and send reservations."""
    # Use the same lock order as SharedStore: process lock, then PostgreSQL lock.
    # Acquiring the database lock first can deadlock an edit racing a send.
    with engine_lock(engine):
        with engine.begin() as connection:
            lock_integration(connection)
            yield connection


class Store(SharedStore):
    def __init__(self, engine: Engine, connection: Connection | None = None):
        super().__init__(engine=engine, connection=connection, initialize=False)

    def put(self, kind: str, key: str, value: dict) -> None:
        # Draft creation and its history commit together in the same database.
        if kind == "activity" and value.get("action") == "draft_created":
            if self.get("enquiries", value["enquiryId"])["source"] != "telegram":
                return super().put(kind, key, value)
            quote = self.get("quotations", value["quotationId"])
            record_activity(
                self.connection, enquiry_id=value["enquiryId"],
                quotation_id=value["quotationId"], version=quote["version"],
                action="quotation_draft_created", result=value["outcome"],
                actor_id="system", role="system", actor_origin="system",
                timestamp=datetime.fromisoformat(value["timestamp"]), event_id=value["id"],
            )
            return
        return super().put(kind, key, value)
