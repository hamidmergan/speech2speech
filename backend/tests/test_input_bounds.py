"""Everything the API takes from outside has a ceiling, and a refusal is a clean 4xx."""

from io import BytesIO

WEBM = b"\x1a\x45\xdf\xa3 audio"

# Larger than SQLite's eight byte integer, so the write would raise OverflowError.
TOO_BIG = 10**25


def _turn(**over):
    turn = {
        "side": "left", "source": "spoken", "original": "Guten Tag",
        "translation": "", "status": "done", "edited": False, "at": 1000,
    }
    turn.update(over)
    return turn


def _session(client) -> str:
    return client.post("/interpreter/sessions", json={}).json()["id"]


def test_a_timestamp_past_the_integer_range_is_refused_cleanly(client):
    """An unbounded at raised OverflowError after the first write of the upsert."""
    sid = _session(client)

    r = client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn(at=TOO_BIG))

    assert r.status_code == 422, r.text
    assert client.get(f"/interpreter/sessions/{sid}").json()["turns"] == []


def test_the_conversation_still_takes_sentences_after_a_refused_timestamp(client):
    """The refused write must not leave the database locked for the next request."""
    sid = _session(client)
    client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn(at=TOO_BIG))

    r = client.put(f"/interpreter/sessions/{sid}/turns/t2", json=_turn(original="Hallo", at=2000))

    assert r.status_code == 200, r.text
    turns = client.get(f"/interpreter/sessions/{sid}").json()["turns"]
    assert [(t["id"], t["original"], t["at"]) for t in turns] == [("t2", "Hallo", 2000)]


def test_a_negative_timestamp_is_refused(client):
    sid = _session(client)
    assert client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn(at=-1)).status_code == 422


def test_a_timestamp_right_at_the_ceiling_is_still_taken(client):
    """The ceiling is the one SQLite can hold, not a round number below it."""
    sid = _session(client)
    at = 2**63 - 1

    r = client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn(at=at))

    assert r.status_code == 200, r.text
    assert client.get(f"/interpreter/sessions/{sid}").json()["turns"][0]["at"] == at


def test_an_endless_turn_id_never_reaches_the_database(client):
    sid = _session(client)

    r = client.put(f"/interpreter/sessions/{sid}/turns/{'t' * 500}", json=_turn())

    assert r.status_code == 422, r.text
    assert client.get(f"/interpreter/sessions/{sid}").json()["turns"] == []


def test_an_endless_session_id_is_refused_before_the_lookup(client):
    assert client.get(f"/interpreter/sessions/{'s' * 500}").status_code == 422
    assert client.delete(f"/interpreter/sessions/{'s' * 500}").status_code == 422
    assert client.patch(f"/interpreter/sessions/{'s' * 500}", json={}).status_code == 422


def test_an_endless_language_code_is_refused_on_every_route(client, models):
    big = "x" * 5000
    sid = _session(client)

    assert client.post("/interpreter/translate", json={"text": "Hallo", "target_lang": big}).status_code == 422
    assert client.post("/interpreter/speak", json={"text": "Hallo", "lang": big}).status_code == 422
    assert client.post("/interpreter/sessions", json={"left_lang": big}).status_code == 422
    assert client.patch(f"/interpreter/sessions/{sid}", json={"right_lang": big}).status_code == 422

    assert models.chat_requests == [] and models.speech_requests == []


def test_an_endless_language_field_on_the_upload_is_refused(client, models):
    r = client.post(
        "/interpreter/transcribe",
        files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")},
        data={"language": "d" * 5000},
    )

    assert r.status_code == 422, r.text
    assert models.transcribe_requests == []


def test_an_endless_locale_query_is_refused(client):
    assert client.post(
        "/interpreter/translate",
        params={"lang": "d" * 5000},
        json={"text": "Hallo", "target_lang": "EN-US"},
    ).status_code == 422
