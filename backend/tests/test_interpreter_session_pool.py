"""The pool of conversations: the newest MAX_SESSIONS stay, the one untouched longest drops out."""

from datetime import timedelta

import pytest

from src.database import get_connection
from src.features.interpreter import repository as repo


@pytest.fixture
def pool_of_five(monkeypatch):
    """A small pool, so a test reaches the edge without writing a hundred rows."""
    monkeypatch.setenv("MAX_SESSIONS", "5")
    return 5


def _create(name: str) -> str:
    return repo.create_session("DE", "EN-US", name, "Guest")["id"]


def _touched(session_id: str, minutes_ago: int) -> None:
    """Sets how long ago a conversation was last used, the pool sorts by that.

    Through repo.now, so the stamp carries the same UTC offset the store writes.
    The sort is lexicographic, and two different offsets would not compare.
    """
    when = (repo.now() - timedelta(minutes=minutes_ago)).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (when, session_id))
        conn.commit()


def test_under_the_limit_everything_stays(pool_of_five):
    ids = [_create(f"P{n}") for n in range(3)]
    stored = {row["id"] for row in repo.list_sessions()}
    assert stored == set(ids)


def test_at_the_limit_the_longest_unused_drops_out(pool_of_five):
    """The pool is filled to the brim, then one more conversation starts."""
    cap = pool_of_five
    ids = [_create(f"P{n}") for n in range(cap)]
    for distance, session_id in enumerate(ids):
        _touched(session_id, cap - distance)
    oldest = ids[0]

    newest = _create("the new one")

    stored = [row["id"] for row in repo.list_sessions()]
    assert len(stored) == cap
    assert oldest not in stored, "the conversation untouched longest has to go"
    assert newest in stored
    assert repo.get_session(oldest) is None, "it is really gone, not only invisible"


def test_a_reopened_conversation_moves_up(pool_of_five):
    """Whoever carries on an old conversation keeps it, the next one in line goes instead."""
    cap = pool_of_five
    ids = [_create(f"P{n}") for n in range(cap)]
    for distance, session_id in enumerate(ids):
        _touched(session_id, cap - distance)
    repo.update_session(ids[0])  # touched again, updated_at is now

    _create("the new one")

    stored = [row["id"] for row in repo.list_sessions()]
    assert ids[0] in stored, "the conversation that was carried on stays"
    assert ids[1] not in stored, "the next oldest goes instead"


def test_the_sentences_of_the_evicted_conversation_go_with_it(pool_of_five):
    """Without the cascade the turns would sit in the table forever with nothing pointing at them."""
    cap = pool_of_five
    victim = _create("gets pushed out")
    repo.upsert_turn(victim, {
        "id": "t-victim", "side": "left", "source": "typed", "original": "Guten Tag",
        "translation": "Good day", "status": "done", "edited": False, "at": 1,
    })
    _touched(victim, 10_000)
    for n in range(cap):
        _create(f"P{n}")

    assert repo.get_session(victim) is None
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM turns WHERE session_id = ?", (victim,)).fetchone()[0]
        assert count == 0


def test_the_default_pool_holds_a_hundred():
    """Without MAX_SESSIONS the installation keeps the same hundred as the source tool."""
    from src.limits import max_sessions

    assert max_sessions() == 100


def test_a_broken_pool_setting_falls_back_to_the_default(monkeypatch):
    from src.limits import max_sessions

    monkeypatch.setenv("MAX_SESSIONS", "not a number")
    assert max_sessions() == 100
    monkeypatch.setenv("MAX_SESSIONS", "0")
    assert max_sessions() == 100


def test_the_list_is_newest_first(pool_of_five):
    ids = [_create(f"P{n}") for n in range(3)]
    for distance, session_id in enumerate(ids):
        _touched(session_id, 10 - distance)

    assert [row["id"] for row in repo.list_sessions()] == list(reversed(ids))
