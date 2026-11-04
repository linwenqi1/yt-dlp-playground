"""SQLite access: one short-lived connection per operation, WAL, no migration framework."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    status            TEXT NOT NULL,
    phase             TEXT,
    url               TEXT NOT NULL,
    platform          TEXT NOT NULL,
    title             TEXT,
    thumbnail_url     TEXT,
    quality           TEXT NOT NULL,
    progress_json     TEXT NOT NULL,
    error_json        TEXT,
    cancel_requested  INTEGER NOT NULL DEFAULT 0,
    output_filename   TEXT,
    output_size_bytes INTEGER,
    content_type      TEXT,
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    finished_at       TEXT,
    expires_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_expires_at ON jobs (expires_at);
"""


@contextmanager
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA user_version = 1")
