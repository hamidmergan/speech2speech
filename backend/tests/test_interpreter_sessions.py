"""Conversations of the interpreter: kept in SQLite, sentences as whole rows, speech windows."""

from io import BytesIO

# A WebM header, so the upload looks like what the browser records.
WEBM = b"\x1a\x45\xdf\xa3 audio"


def _turn(side, original, at=1000):
    return {"side": side, "source": "typed", "original": original, "translation": "", "status": "done", "edited": False, "at": at}


def test_create_a_conversation_and_save_a_sentence(client):
    r = client.post("/interpreter/sessions", json={"left_name": "Reception"})
    assert r.status_code == 200, r.text
    state = r.json()
    assert state["turns"] == [] and state["ended"] is False

    r = client.put(f"/interpreter/sessions/{state['id']}/turns/t1", json=_turn("left", "Guten Tag"))
    assert r.status_code == 200, r.text
    assert r.json()["original"] == "Guten Tag"

    # The same sentence written again replaces the first version.
    client.put(f"/interpreter/sessions/{state['id']}/turns/t1", json={**_turn("left", "Guten Tag!"), "translation": "Hello!"})
    r = client.get(f"/interpreter/sessions/{state['id']}")
    assert [(t["original"], t["translation"]) for t in r.json()["turns"]] == [("Guten Tag!", "Hello!")]

    r = client.get("/interpreter/sessions")
    assert r.json()["sessions"][0]["first_original"] == "Guten Tag!"
    assert r.json()["sessions"][0]["first_translation"] == "Hello!"
    assert r.json()["sessions"][0]["turn_count"] == 1


def test_the_names_and_languages_come_back(client):
    r = client.post("/interpreter/sessions", json={
        "left_lang": "EN-US", "right_lang": "DE", "left_name": "Ada", "right_name": "Bo",
    })
    state = r.json()
    assert (state["left_lang"], state["right_lang"]) == ("EN-US", "DE")
    assert (state["left_name"], state["right_name"]) == ("Ada", "Bo")

    client.patch(f"/interpreter/sessions/{state['id']}", json={"right_name": "Bea"})
    assert client.get(f"/interpreter/sessions/{state['id']}").json()["right_name"] == "Bea"


def test_an_unknown_language_is_refused_on_create_and_on_patch(client):
    assert client.post("/interpreter/sessions", json={"left_lang": "FR"}).status_code == 400
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    assert client.patch(f"/interpreter/sessions/{sid}", json={"right_lang": "IT"}).status_code == 400


def test_a_sentence_typed_away_to_nothing_disappears_again(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn("left", "Hal"))
    r = client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn("left", "   "))
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert client.get(f"/interpreter/sessions/{sid}").json()["turns"] == []


def test_an_ended_conversation_takes_no_further_sentence(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    r = client.patch(f"/interpreter/sessions/{sid}", json={"ended": True})
    assert r.json()["ended"] is True
    assert client.put(f"/interpreter/sessions/{sid}/turns/t9", json=_turn("left", "One more")).status_code == 409
    # Reopening it lets the conversation carry on.
    assert client.patch(f"/interpreter/sessions/{sid}", json={"ended": False}).json()["ended"] is False
    assert client.put(f"/interpreter/sessions/{sid}/turns/t9", json=_turn("left", "One more")).status_code == 200


def _fill(client, sid):
    """Five sentences of four thousand characters, that is exactly the limit."""
    for i in range(5):
        r = client.put(f"/interpreter/sessions/{sid}/turns/t{i}", json=_turn("left", "a" * 4000, at=i))
        assert r.status_code == 200, r.text


def test_a_full_conversation_takes_no_further_sentence(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    _fill(client, sid)
    r = client.put(f"/interpreter/sessions/{sid}/turns/t9", json=_turn("left", "One more", at=9))
    assert r.status_code == 409
    # Refused outright, never written short.
    turns = client.get(f"/interpreter/sessions/{sid}").json()["turns"]
    assert len(turns) == 5
    assert all(len(t["original"]) == 4000 for t in turns)


def test_a_correction_does_not_count_twice(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    _fill(client, sid)
    # The old version of this sentence leaves the count, so a correction always fits.
    assert client.put(f"/interpreter/sessions/{sid}/turns/t0", json=_turn("left", "a" * 4000, at=0)).status_code == 200
    assert client.put(f"/interpreter/sessions/{sid}/turns/t0", json=_turn("left", "Short", at=0)).status_code == 200
    assert client.get(f"/interpreter/sessions/{sid}").json()["turns"][0]["original"] == "Short"


def test_a_spoken_sentence_corrected_by_hand_is_marked(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    client.put(f"/interpreter/sessions/{sid}/turns/t1", json={
        **_turn("right", "Gutn Tag"), "source": "spoken",
    })
    client.put(f"/interpreter/sessions/{sid}/turns/t1", json={
        **_turn("right", "Guten Tag"), "source": "spoken", "edited": True,
    })
    turn = client.get(f"/interpreter/sessions/{sid}").json()["turns"][0]
    assert (turn["original"], turn["edited"], turn["source"]) == ("Guten Tag", True, "spoken")


def test_an_unknown_conversation_stays_a_404(client):
    assert client.get("/interpreter/sessions/nothing-here").status_code == 404
    assert client.put("/interpreter/sessions/nothing-here/turns/t1", json=_turn("left", "Hi")).status_code == 404


def test_deleting_takes_the_conversation_out_of_the_list(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    assert client.delete(f"/interpreter/sessions/{sid}").status_code == 204
    assert client.get("/interpreter/sessions").json()["sessions"] == []
    assert client.delete(f"/interpreter/sessions/{sid}").status_code == 404


def test_the_sentences_go_with_the_deleted_conversation(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn("left", "Guten Tag"))
    client.delete(f"/interpreter/sessions/{sid}")

    from src.features.interpreter import repository as repo
    assert repo.list_turns(sid) == [], "without the cascade the sentences would sit there forever"


def test_the_sentences_keep_their_order(client):
    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    for turn_id, at in (("t3", 3000), ("t1", 1000), ("t2", 2000)):
        client.put(f"/interpreter/sessions/{sid}/turns/{turn_id}", json=_turn("left", turn_id, at=at))
    assert [t["id"] for t in client.get(f"/interpreter/sessions/{sid}").json()["turns"]] == ["t1", "t2", "t3"]


def test_a_speech_window_comes_back_as_text(client, models):
    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")})
    assert r.status_code == 200, r.text
    # The JSON object a short clip comes back as is unwrapped to its text.
    assert r.json()["text"] == "Hallo Welt"
    assert models.transcribe_requests[0]["language"] is None
    assert models.transcribe_requests[0]["model"] == "stt-test"


def test_a_speech_window_hands_the_model_the_language(client, models):
    audio = {"audio": ("window.webm", BytesIO(WEBM), "audio/webm")}
    r = client.post("/interpreter/transcribe", files=audio, data={"language": "DE"})
    assert r.status_code == 200, r.text
    assert models.transcribe_requests[0]["language"] == "de"
    # Anything that is not a two-letter code stays away from the model.
    client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")}, data={"language": "deutsch"})
    assert models.transcribe_requests[1]["language"] is None


def test_an_empty_recording_is_not_sent_at_all(client, models):
    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(b""), "audio/webm")})
    assert r.status_code == 200 and r.json()["text"] == ""
    assert models.transcribe_requests == [], "silence would only make the model invent a sentence"


def test_a_plain_text_answer_arrives_unwrapped(client, models):
    models.heard = "Guten Tag, wie geht es Ihnen?"
    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")})
    assert r.json()["text"] == "Guten Tag, wie geht es Ihnen?"


def test_without_a_speech_model_the_microphone_says_so(client, monkeypatch):
    monkeypatch.delenv("STT_MODEL")
    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")})
    assert r.status_code == 503


def test_a_failing_speech_model_answers_502(client, models):
    models.fail_paths.add("/v1/audio/transcriptions")
    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(WEBM), "audio/webm")})
    assert r.status_code == 502
