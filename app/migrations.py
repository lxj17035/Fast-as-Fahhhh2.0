"""Small, non-destructive upgrade for existing PostgreSQL delivery history."""
from sqlalchemy import inspect, text
from app.database import send_attempts
from app.xinjie_store import integration_transaction


def upgrade_delivery_schema(engine):
    # Runtime is PostgreSQL. SQLite is a fresh-schema test adapter only.
    if engine.dialect.name != "postgresql":
        return
    with integration_transaction(engine) as connection:
        connection.execute(text(
            "ALTER TABLE send_attempts ADD COLUMN IF NOT EXISTS "
            "retry_of_attempt_id VARCHAR(36) REFERENCES send_attempts(id)"
        ))
        # Old releases constrained quotation_id alone. Keep rows, PDF bytes and
        # activity foreign keys, replacing only that obsolete uniqueness rule.
        for constraint in inspect(connection).get_unique_constraints("send_attempts"):
            if constraint["column_names"] == ["quotation_id"]:
                quoted = connection.dialect.identifier_preparer.quote(constraint["name"])
                connection.execute(text(f"ALTER TABLE send_attempts DROP CONSTRAINT {quoted}"))
        for index in send_attempts.indexes:
            index.create(connection, checkfirst=True)
