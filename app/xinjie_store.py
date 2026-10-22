"""Adapt Xinjie's record API to the application's existing SQLAlchemy database."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from threading import Lock, RLock
from weakref import WeakKeyDictionary

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, Engine

from app.activity import record_activity
from app.database import enquiries, telegram_updates, xinjie_records
from backend.errors import AppError

_engine_locks = WeakKeyDictionary()
_locks_guard = Lock()
_ADVISORY_LOCK = 731929001


def _sqlite_lock(engine: Engine):
    with _locks_guard:
        if engine not in _engine_locks:
            _engine_locks[engine] = RLock()
        return _engine_locks[engine]


def lock_integration(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK}
        )


@contextmanager
def integration_transaction(engine: Engine):
    """Serialize prototype version checks, edits, previews and send reservations."""
    if engine.dialect.name == "sqlite":
        with _sqlite_lock(engine):
            with engine.begin() as connection:
                yield connection
    else:
        with engine.begin() as connection:
            lock_integration(connection)
            yield connection


class Store:
    def __init__(self, engine: Engine, connection: Connection | None = None):
        self.engine = engine
        self.connection = connection

    @contextmanager
    def transaction(self):
        if self.connection is not None:
            lock_integration(self.connection)
            yield self
            return
        with integration_transaction(self.engine) as connection:
            self.connection = connection
            try:
                yield self
            finally:
                self.connection = None

    @contextmanager
    def _reader(self):
        if self.connection is not None:
            yield self.connection
        else:
            with self.engine.connect() as connection:
                yield connection

    @staticmethod
    def _enquiry_query():
        return select(enquiries, telegram_updates).join(
            telegram_updates,
            enquiries.c.telegram_update_id == telegram_updates.c.update_id,
        )

    @staticmethod
    def _enquiry(row):
        return {
            "id": row["id"],
            "text": row["original_text"],
            # Explicit fictional demo association, never inferred identity.
            "clientId": "demo-client",
            "source": row["source"],
            "chatId": str(row["chat_id"]),
            "status": row["status"],
        }

    def get(self, kind: str, key: str):
        with self._reader() as connection:
            if kind == "enquiries":
                row = connection.execute(
                    self._enquiry_query().where(enquiries.c.id == key)
                ).mappings().one_or_none()
                if row is not None:
                    return self._enquiry(row)
            else:
                row = connection.execute(
                    select(xinjie_records.c.body).where(
                        xinjie_records.c.kind == kind, xinjie_records.c.id == key
                    )
                ).one_or_none()
                if row is not None:
                    return deepcopy(row.body)
        raise AppError("Record not found", 404)

    def list(self, kind: str):
        with self._reader() as connection:
            if kind == "enquiries":
                rows = connection.execute(
                    self._enquiry_query().order_by(enquiries.c.id)
                ).mappings().all()
                return [self._enquiry(row) for row in rows]
            rows = connection.execute(
                select(xinjie_records.c.body)
                .where(xinjie_records.c.kind == kind)
                .order_by(xinjie_records.c.kind, xinjie_records.c.id)
            ).all()
            return [deepcopy(row.body) for row in rows]

    def put(self, kind: str, key: str, value: dict) -> None:
        if self.connection is None:
            raise RuntimeError("Record writes require a transaction")
        if kind == "activity":
            # Normalize Xinjie's real draft event into the one activity stream.
            # Keep their service source unchanged and avoid a second event copy.
            if value.get("action") != "draft_created":
                raise AppError("Unsupported service activity")
            quote = self.get("quotations", value["quotationId"])
            record_activity(
                self.connection,
                enquiry_id=value["enquiryId"],
                quotation_id=value["quotationId"],
                version=quote["version"],
                action="quotation_draft_created",
                result=value["outcome"],
                actor_id="system",
                role="system",
                actor_origin="system",
                timestamp=datetime.fromisoformat(value["timestamp"]),
                event_id=value["id"],
            )
            return
        if kind == "enquiries":
            current = self.get(kind, key)
            if value.get("status") != "needs_review":
                raise AppError("Unsupported enquiry update")
            if current["status"] != "needs_review":
                raise AppError("Enquiry delivery is locked or unresolved", 409)
            self.connection.execute(
                enquiries.update().where(enquiries.c.id == key)
                .values(status="needs_review")
            )
            return
        insert = (
            pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        )
        statement = insert(xinjie_records).values(kind=kind, id=key, body=value)
        self.connection.execute(
            statement.on_conflict_do_update(
                index_elements=["kind", "id"], set_={"body": statement.excluded.body}
            )
        )
