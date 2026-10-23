"""The two tables of a conversation, in one SQLite file under DATA_DIR.

SQLite takes one writer at a time, which is why the backend runs a single web
process. WAL mode lets readers through while that writer works.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

DB_FILENAME = "speech2speech.sqlite3"

# One connection per thread. FastAPI answers def routes on a thread pool, and a
# SQLite connection must not travel between threads.
_local = threading.local()
_lock = threading.Lock()
_ready = False


def data_dir() -> Path:
    """Where the database file lives. The compose file mounts a volume on it."""
    return Path((os.environ.get("DATA_DIR") or "").strip() or "data")


def db_path() -> Path:
    return data_dir() / DB_FILENAME


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    left_lang   TEXT NOT NULL,
    right_lang  TEXT NOT NULL,
    left_name   TEXT NOT NULL DEFAULT '',
    right_name  TEXT NOT NULL DEFAULT '',
    ended_at    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    side        TEXT NOT NULL,
    source      TEXT NOT NULL,
    original    TEXT NOT NULL,
    translation TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL,
    edited      INTEGER NOT NULL DEFAULT 0,
    at          INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS turns_by_session ON turns (session_id, at, created_at);
CREATE INDEX IF NOT EXISTS sessions_by_use ON sessions (updated_at DESC);
"""


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Readers never wait for the writer, and a sentence is on disk once it is written.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    # Without this the cascade from sessions to turns would not fire.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Creates the schema. Safe to call more than once."""
    global _ready
    with _lock:
        conn = _connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        _ready = True


def reset_for_tests() -> None:
    """Drops the cached connections, so a test may point DATA_DIR somewhere else."""
    global _ready
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
        _local.path = None
    _ready = False


@contextmanager
def get_connection():
    """The connection of this thread, with the schema in place."""
    if not _ready:
        init_db()
    path = str(db_path())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if conn is not None:
            conn.close()
        conn = _connect()
        _local.conn = conn
        _local.path = path
    yield conn
