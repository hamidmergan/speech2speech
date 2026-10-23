"""The storage layer itself: rollback on an error, and more than one thread at a time."""

import queue
import shutil
import sqlite3
import threading

import pytest

from src import database
from src.database import get_connection

STAMP = "2026-01-01T00:00:00"


def _insert(conn, session_id: str, name: str) -> None:
    conn.execute(
        """INSERT INTO sessions (id, left_lang, right_lang, left_name, right_name, created_at, updated_at)
           VALUES (?, 'DE', 'EN-US', ?, '', ?, ?)""",
        (session_id, name, STAMP, STAMP),
    )


def _write(session_id: str, name: str) -> None:
    with get_connection() as conn:
        _insert(conn, session_id, name)
        conn.commit()


def _names() -> list[str]:
    with get_connection() as conn:
        return [row["left_name"] for row in conn.execute("SELECT left_name FROM sessions ORDER BY id")]


class Worker:
    """One thread that stays alive between calls, the way the route pool does.

    A fresh thread per call would never show a cached connection, because the
    cache is thread local and a new thread starts with nothing in it.
    """

    def __init__(self):
        self._jobs: queue.Queue = queue.Queue()
        self._results: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            work = self._jobs.get()
            if work is None:
                database.close_thread_connection()
                self._results.put(("value", None))
                return
            try:
                self._results.put(("value", work()))
            except BaseException as e:  # noqa: BLE001 - the test wants to see it
                self._results.put(("error", e))

    def run(self, work):
        self._jobs.put(work)
        kind, payload = self._results.get(timeout=20)
        if kind == "error":
            raise payload
        return payload

    def close(self):
        self._jobs.put(None)
        self._results.get(timeout=20)
        self._thread.join(20)


@pytest.fixture
def worker():
    w = Worker()
    yield w
    w.close()


def _in_thread(work):
    """Runs work once on a thread of its own and hands back what it returned."""
    w = Worker()
    try:
        return w.run(work)
    finally:
        w.close()


def test_an_error_inside_the_block_rolls_the_write_back():
    """The orphaned statement must not be committed later by an unrelated request."""
    database.init_db()
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            _insert(conn, "orphan", "ORPHAN")
            raise RuntimeError("the route died between the write and the commit")

    _write("real", "Reception")

    assert _names() == ["Reception"]


def test_an_error_leaves_the_connection_usable_for_the_next_thread():
    """An open transaction would hold the write lock of the whole file."""
    database.init_db()
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            _insert(conn, "orphan", "ORPHAN")
            raise RuntimeError("the route died between the write and the commit")

    def other_thread():
        with get_connection() as conn:
            # A short wait, so a held write lock fails the test in a second
            # instead of sitting out the thirty second default.
            conn.execute("PRAGMA busy_timeout = 1500")
            _insert(conn, "from-the-other-thread", "Visitor")
            conn.commit()
        return True

    assert _in_thread(other_thread) is True
    assert _names() == ["Visitor"]


def test_two_threads_write_at_the_same_time_and_both_sentences_survive():
    """Writers serialize, which is the defining property of the new storage."""
    database.init_db()
    _write("a-seed", "Seed")
    ready = threading.Barrier(4)

    def writer(n: int):
        def work():
            with get_connection() as conn:
                conn.execute("PRAGMA busy_timeout = 10000")
                ready.wait(10)
                _insert(conn, f"s{n}", f"Speaker {n}")
                conn.commit()
            return True
        return work

    threads = [threading.Thread(target=_in_thread, args=(writer(n),)) for n in range(3)]
    for thread in threads:
        thread.start()
    ready.wait(10)
    for thread in threads:
        thread.join(20)
        assert not thread.is_alive()

    assert _names() == ["Seed", "Speaker 0", "Speaker 1", "Speaker 2"]


def test_a_connection_that_cannot_be_rolled_back_is_thrown_away():
    """A broken connection must not stay cached for the life of the thread."""
    database.init_db()
    with get_connection() as conn:
        first = conn

    with pytest.raises(sqlite3.ProgrammingError):
        with get_connection() as conn:
            conn.close()
            conn.execute("SELECT 1")

    with get_connection() as conn:
        assert conn is not first
        assert conn.execute("SELECT 1").fetchone()[0] == 1


def test_a_reset_reaches_the_worker_threads_too(worker, tmp_path, monkeypatch):
    """The fixture points DATA_DIR at a fresh folder, and the route threads must follow."""
    folder = tmp_path / "shared-name"
    monkeypatch.setenv("DATA_DIR", str(folder))
    database.reset_for_tests()
    _write("first", "First")

    # The worker thread caches a connection to this file.
    assert worker.run(_names) == ["First"]

    # The next test wipes the folder and reuses the very same path, so the path
    # alone tells the worker nothing.
    database.reset_for_tests()
    shutil.rmtree(folder)
    database.init_db()
    _write("second", "Second")

    assert worker.run(_names) == ["Second"]


def test_the_columns_carry_the_defaults_of_the_schema():
    """A write that leaves a column out gets the documented value, not an error."""
    database.init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES ('s', ?, ?)",
            (STAMP, STAMP),
        )
        conn.execute(
            """INSERT INTO turns (id, session_id, side, original, at, created_at, updated_at)
               VALUES ('t', 's', 'left', 'Guten Tag', 1000, ?, ?)""",
            (STAMP, STAMP),
        )
        conn.commit()
        session = conn.execute("SELECT * FROM sessions WHERE id = 's'").fetchone()
        turn = conn.execute("SELECT * FROM turns WHERE id = 't'").fetchone()

    assert (session["left_lang"], session["right_lang"]) == ("DE", "EN-US")
    assert (turn["source"], turn["status"]) == ("spoken", "done")
