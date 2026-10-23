"""Conversations of the interpreter and their sentences in the database."""

import sqlite3
import uuid
from datetime import datetime

from src.database import get_connection
from src.limits import max_sessions

SESSION_FIELDS = ("left_lang", "right_lang", "left_name", "right_name", "ended_at")

# The timestamp columns are text in SQLite, read back as datetime so the callers
# see the same values they would get from any other database.
_TIMESTAMPS = ("created_at", "updated_at", "ended_at")


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for name in _TIMESTAMPS:
        if name in out and isinstance(out[name], str):
            out[name] = datetime.fromisoformat(out[name])
    return out


def _stamp(value) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def create_session(left_lang: str, right_lang: str, left_name: str, right_name: str) -> dict:
    """The new conversation is written, then the installation is trimmed back to the pool."""
    session_id = uuid.uuid4().hex
    now_text = now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sessions (id, left_lang, right_lang, left_name, right_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, left_lang, right_lang, left_name, right_name, now_text, now_text),
        )
        _evict_oldest(conn)
        conn.commit()
        return _row(conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())


def _evict_oldest(conn, cap: int | None = None) -> int:
    """Everything past the newest cap conversations goes, sentences follow by cascade."""
    limit = cap if cap is not None else max_sessions()
    cursor = conn.execute(
        """DELETE FROM sessions
            WHERE id NOT IN (SELECT id FROM sessions
                             ORDER BY updated_at DESC, id DESC LIMIT ?)""",
        (limit,),
    )
    return cursor.rowcount


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        return _row(conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())


def list_sessions(limit: int | None = None) -> list[dict]:
    """The conversations, newest first, with the first sentence and the count."""
    cap = limit if limit is not None else max_sessions()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT s.*,
                      (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id) AS turn_count,
                      (SELECT t.original FROM turns t WHERE t.session_id = s.id
                         ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_original,
                      (SELECT t.side FROM turns t WHERE t.session_id = s.id
                         ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_side,
                      (SELECT t.translation FROM turns t WHERE t.session_id = s.id
                         ORDER BY t.at ASC, t.created_at ASC LIMIT 1) AS first_translation
               FROM sessions s
               ORDER BY s.updated_at DESC, s.id DESC
               LIMIT ?""",
            (cap,),
        ).fetchall()
        return [_row(row) for row in rows]


def update_session(session_id: str, **fields) -> dict | None:
    unknown = set(fields) - set(SESSION_FIELDS)
    if unknown:
        raise ValueError(f"unknown session fields: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    values = [_stamp(value) for value in fields.values()]
    with get_connection() as conn:
        conn.execute(
            f"""UPDATE sessions
                SET {assignments + ', ' if assignments else ''}updated_at = ?
                WHERE id = ?""",
            (*values, now().isoformat(), session_id),
        )
        conn.commit()
        return _row(conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())


def delete_session(session_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def upsert_turn(session_id: str, turn: dict) -> dict:
    """Writes a sentence as a whole, a repeated write replaces text, translation and status."""
    now_text = now().isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now_text, session_id))
        conn.execute(
            """INSERT INTO turns
                   (id, session_id, side, source, original, translation, status, edited, at,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (id) DO UPDATE SET
                   original = excluded.original,
                   translation = excluded.translation,
                   status = excluded.status,
                   edited = excluded.edited,
                   updated_at = excluded.updated_at""",
            (
                turn["id"], session_id, turn["side"], turn["source"], turn["original"],
                turn["translation"], turn["status"], int(turn["edited"]), turn["at"],
                now_text, now_text,
            ),
        )
        conn.commit()
        return _row(conn.execute("SELECT * FROM turns WHERE id = ?", (turn["id"],)).fetchone())


def delete_turn(session_id: str, turn_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM turns WHERE id = ? AND session_id = ?", (turn_id, session_id))
        conn.commit()


def list_turns(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY at ASC, created_at ASC",
            (session_id,),
        ).fetchall()
        return [_row(row) for row in rows]


def now() -> datetime:
    return datetime.now()
