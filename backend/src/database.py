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

from loguru import logger

DB_FILENAME = "speech2speech.sqlite3"

# One connection per thread. FastAPI answers def routes on a thread pool, and a
# SQLite connection must not travel between threads.
_local = threading.local()
_lock = threading.RLock()
_ready = False
# Bumped by reset_for_tests. A thread whose connection carries an older number
# opens a fresh one, so a reset reaches the worker threads and not only the
# thread that called it. A connection may only be closed by its own thread, so
# this is the one way to retire a connection that another thread holds.
_generation = 0


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
    # Readers never wait for the writer. NORMAL survives a crash of this process,
    # but it does not flush on every commit, so a power cut can cost the newest
    # transactions. FULL would be the setting that puts a sentence on disk.
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


def close_thread_connection() -> None:
    """Closes the connection of the calling thread, if it has one."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error as e:
            logger.warning("Closing the database connection failed: {}", e)
    _local.conn = None
    _local.path = None


def reset_for_tests() -> None:
    """Retires every cached connection, so a test may point DATA_DIR somewhere else.

    The calling thread's connection is closed here. The connections of the other
    threads cannot be closed from here, because sqlite3 binds a connection to the
    thread that created it. They are retired by the generation counter instead:
    each of those threads closes its own connection the next time it asks for one.
    """
    global _ready, _generation
    close_thread_connection()
    with _lock:
        _generation += 1
    _ready = False


@contextmanager
def get_connection():
    """The connection of this thread, with the schema in place.

    An exception inside the block rolls the transaction back. Without that the
    cached connection would stay in an open transaction and hold the write lock
    of the whole file, and the orphaned statement would be committed later by an
    unrelated request. A connection that cannot be rolled back is thrown away.
    """
    if not _ready:
        init_db()
    path = str(db_path())
    conn = getattr(_local, "conn", None)
    stale = getattr(_local, "generation", None) != _generation
    if conn is None or stale or getattr(_local, "path", None) != path:
        if conn is not None:
            close_thread_connection()
        conn = _connect()
        _local.conn = conn
        _local.path = path
        _local.generation = _generation
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception as rollback_error:
            # The connection is unusable. Drop it, the next call opens a fresh one.
            logger.error("Database rollback failed, the connection is dropped: {}", rollback_error)
            if getattr(_local, "conn", None) is conn:
                close_thread_connection()
        raise
