from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from signal_desk.config import DB_PATH, MIGRATIONS

_migration_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def reader() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def initialize() -> None:
    with _migration_lock:
        connection = connect()
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )"""
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
        finally:
            connection.close()
        for path in sorted(Path(MIGRATIONS).glob("*.sql")):
            version = int(path.name.split("_", 1)[0])
            if version in applied:
                continue
            script = path.read_text(encoding="utf-8")
            connection = connect()
            try:
                connection.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + script
                    + f"\nINSERT INTO schema_migrations(version, applied_at) "
                    + f"VALUES ({version}, strftime('%Y-%m-%dT%H:%M:%fZ','now'));\nCOMMIT;"
                )
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
