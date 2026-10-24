"""Quotation records in shared PostgreSQL. SQLite is test/fixture injection only."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock, Lock
from weakref import WeakKeyDictionary

from sqlalchemy import Column, DateTime, JSON, MetaData, String, Table, create_engine, select, text
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.pool import StaticPool

from app.db_url import postgres_url
from app.database import metadata as inbound_metadata, enquiries, telegram_updates, message_links
from .errors import AppError
from .settings import profile_id, require_profile

metadata = MetaData()
records = Table(
    "quotation_records", metadata,
    Column("kind", String(40), primary_key=True),
    Column("id", String(160), primary_key=True),
    Column("body", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
# A short transaction lock serializes prototype mutations across processes,
# including absent-row creation and check-version-then-update operations.
# PostgreSQL releases it automatically at transaction commit/rollback.
WRITE_LOCK = 7081942026
_engine_locks = WeakKeyDictionary()
_locks_guard = Lock()

def engine_lock(engine):
    with _locks_guard:
        if engine not in _engine_locks:
            _engine_locks[engine] = RLock()
        return _engine_locks[engine]


class Store:
    def __init__(self, database_url=None, *, engine=None, connection=None, initialize=True):
        self.lock = RLock()
        self.connection = connection
        self.owns_engine = engine is None
        self.engine = engine if engine is not None else create_engine(
            postgres_url(database_url if database_url is not None else os.environ.get("DATABASE_URL", "")),
            pool_pre_ping=True,
        )
        self.lock = engine_lock(self.engine)
        if not initialize:
            return
        with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK})
            metadata.create_all(connection)
            inbound_metadata.create_all(connection)

    @classmethod
    def for_test(cls, path=None):
        """Explicit isolated SQLite adapter for tests/offline PDF fixtures only."""
        options = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if path is None:
            options["poolclass"] = StaticPool
        engine = create_engine("sqlite://" if path is None else f"sqlite:///{path}", **options)
        store = cls(engine=engine)
        store.owns_engine = True
        return store

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.connection is not None:
                yield self
                return
            with self.engine.begin() as connection:
                self.connection = connection
                try:
                    if self.engine.dialect.name == "postgresql":
                        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WRITE_LOCK})
                    yield self
                finally:
                    self.connection = None

    @contextmanager
    def reading(self):
        with self.lock:
            if self.connection is not None:
                yield self.connection
            else:
                with self.engine.connect() as connection:
                    yield connection

    def inbound(self, connection, key=None):
        statement = select(enquiries, telegram_updates).join(
            telegram_updates, enquiries.c.telegram_update_id == telegram_updates.c.update_id)
        if key is not None:
            statement = statement.where(enquiries.c.id == key)
        result = []
        for row in connection.execute(statement).mappings():
            messages = connection.execute(select(telegram_updates.c.original_text, telegram_updates.c.update_id).join(
                message_links, message_links.c.update_id == telegram_updates.c.update_id
            ).where(message_links.c.enquiry_id == row["id"])
                .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).mappings().all()
            context = connection.execute(select(records.c.body).where(
                records.c.kind == "enquiry_context", records.c.id == row["id"])).scalar_one_or_none() or {}
            unresolved = connection.execute(select(message_links.c.update_id).join(
                telegram_updates, message_links.c.update_id == telegram_updates.c.update_id
            ).where(message_links.c.business_profile_id == row["business_profile_id"],
                    telegram_updates.c.chat_id == row["chat_id"], message_links.c.status == "needs_assignment")
                .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).scalars().all()
            result.append({"id": row["id"], "text": "\n\n".join(m["original_text"] for m in messages) if messages else row["original_text"], "source": row["source"],
                           "messageUpdateIds": [str(m["update_id"]) for m in messages] if messages else [str(row["update_id"])],
                           "unassignedMessageIds": [str(identity) for identity in unresolved],
                           "business_profile_id": row["business_profile_id"],
                           "chatId": str(row["chat_id"]), "clientId": context.get("clientId"),
                           "providerUpdateId": str(row["update_id"]),
                           "providerMessageId": str(row["message_id"]), "status": row["status"]})
        return result

    def get(self, kind, key):
        with self.reading() as connection:
            if kind == "enquiries":
                inbound = self.inbound(connection, key)
                if inbound:
                    return inbound[0]
            value = connection.execute(select(records.c.body).where(
                records.c.kind == kind, records.c.id == key)).scalar_one_or_none()
        if value is None:
            raise AppError(f"{kind} not found", 404)
        if kind in {"enquiries", "clients", "quotations"}:
            value.setdefault("business_profile_id", "printing")
        return value

    def put(self, kind, key, value):
        if self.connection is None:
            raise RuntimeError("Store mutations require transaction()")
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if kind in {"enquiries", "clients", "quotations"}:
            identity = profile_id(value.get("business_profile_id", "printing"))
            try:
                original = self.get(kind, key)
            except AppError as error:
                if error.status != 404:
                    raise
            else:
                if original["business_profile_id"] != identity:
                    raise AppError("Business profile cannot be changed on an existing record", 409)
            value = {**value, "business_profile_id": identity}
            client_id = value.get("clientId") if kind == "enquiries" else None
            if kind == "quotations":
                client_id = value.get("client", {}).get("id")
                try:
                    parent = self.get("enquiries", value["enquiryId"])
                except AppError as error:
                    if error.status != 404:
                        raise
                else:
                    require_profile(parent, identity)
            if client_id:
                require_profile(self.get("clients", client_id), identity)
        if kind == "enquiries" and self.inbound(self.connection, key):
            # Do not overwrite transport identifiers or the original message.
            if "status" in value:
                self.connection.execute(enquiries.update().where(enquiries.c.id == key).values(status=value["status"]))
            return self.put("enquiry_context", key, {"clientId": value.get("clientId")})
        insert = pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
        statement = insert(records).values(kind=kind, id=key, body=value,
                                          created_at=datetime.now(timezone.utc))
        self.connection.execute(statement.on_conflict_do_update(
            index_elements=[records.c.kind, records.c.id], set_={"body": statement.excluded.body}))

    def list(self, kind):
        with self.reading() as connection:
            values = list(connection.execute(select(records.c.body).where(
                records.c.kind == kind).order_by(records.c.created_at, records.c.id)).scalars())
            if kind in {"enquiries", "clients", "quotations"}:
                for value in values:
                    value.setdefault("business_profile_id", "printing")
            if kind == "enquiries":
                inbound = self.inbound(connection)
                ids = {item["id"] for item in inbound}
                return inbound + [item for item in values if item["id"] not in ids]
            return values

    def close(self):
        if self.owns_engine:
            self.engine.dispose()
