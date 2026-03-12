from __future__ import annotations

from pathlib import Path
import sqlite3

from onlydev.core.migrations import MIGRATIONS


def connect(db_path: str | Path = "jobs.db") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (version INTEGER PRIMARY KEY);"
    )
    conn.commit()

    applied = {row[0] for row in conn.execute("SELECT version FROM _migrations")}

    for i, sql in enumerate(MIGRATIONS):
        if i not in applied:
            conn.executescript(sql)
            conn.execute("INSERT INTO _migrations (version) VALUES (?)", (i,))
            conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    run_migrations(conn)