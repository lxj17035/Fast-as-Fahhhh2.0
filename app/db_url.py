"""Normalize PostgreSQL URLs without exposing credentials in errors."""
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def postgres_url(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("DATABASE_URL is required")
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    try:
        url = make_url(value)
        if url.drivername not in ("postgresql", "postgresql+psycopg"):
            raise ValueError()
        return url.set(drivername="postgresql+psycopg")
    except (ArgumentError, ValueError, TypeError):
        raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL") from None
