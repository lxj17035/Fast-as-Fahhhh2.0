import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from .errors import AppError


class Store:
    """One SQLite connection protected across the local HTTP server's threads.

    Mutations must be enclosed in transaction(). Composite operations then stay
    atomic, including version checks. JSON records keep this prototype small.
    """

    def __init__(self, path="data/quotation.sqlite3"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.depth = 0
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.execute("""CREATE TABLE IF NOT EXISTS records (
            kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY(kind, id))""")
        self.connection.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            outer = self.depth == 0
            if outer:
                self.connection.execute("BEGIN IMMEDIATE")
            self.depth += 1
            try:
                yield self
                if outer:
                    self.connection.commit()
            except BaseException:
                if outer:
                    self.connection.rollback()
                raise
            finally:
                self.depth -= 1

    def get(self, kind, key):
        with self.lock:
            row = self.connection.execute(
                "SELECT body FROM records WHERE kind=? AND id=?", (kind, key)
            ).fetchone()
        if row is None:
            raise AppError(f"{kind} not found", 404)
        return json.loads(row[0])

    def put(self, kind, key, value):
        self.connection.execute(
            "INSERT INTO records VALUES (?, ?, ?) "
            "ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body",
            (kind, key, json.dumps(value, ensure_ascii=False, allow_nan=False)),
        )

    def list(self, kind):
        with self.lock:
            rows = self.connection.execute(
                "SELECT body FROM records WHERE kind=? ORDER BY rowid", (kind,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def close(self):
        self.connection.close()
