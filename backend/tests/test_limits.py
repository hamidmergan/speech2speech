"""The ceilings. None of them cuts anything away, every one of them says so instead."""

from io import BytesIO

WEBM = b"\x1a\x45\xdf\xa3"


def _turn(original, at=1000):
    return {"side": "left", "source": "typed", "original": original, "translation": "", "status": "done", "edited": False, "at": at}


def test_a_recording_past_the_ceiling_is_refused(client, models, monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_BYTES", "1000")
    audio = WEBM + b"\x00" * 5000

    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(audio), "audio/webm")})

    assert r.status_code == 413
    assert r.json()["detail"], "the page shows this sentence instead of a shortened transcript"
    assert models.transcribe_requests == [], "nothing of it reaches the model"


def test_a_recording_that_crosses_the_ceiling_mid_stream_is_refused(client, models, monkeypatch):
    """The upload is read in chunks of a megabyte, so the ceiling has to hold inside the loop."""
    monkeypatch.setenv("MAX_AUDIO_BYTES", str(1_500_000))
    audio = WEBM + b"\x00" * (3 * 1024 * 1024)

    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(audio), "audio/webm")})

    assert r.status_code == 413
    assert models.transcribe_requests == []


def test_a_recording_under_the_ceiling_goes_through_whole(client, models, monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_BYTES", str(3 * 1024 * 1024))
    audio = WEBM + b"\x00" * (2 * 1024 * 1024)

    r = client.post("/interpreter/transcribe", files={"audio": ("window.webm", BytesIO(audio), "audio/webm")})

    assert r.status_code == 200, r.text
    assert len(models.transcribe_requests) == 1
    # The whole recording arrived, the multipart wrapper makes it a little larger.
    assert models.transcribe_requests[0]["size"] >= len(audio)


def test_the_default_audio_ceiling_is_thirty_megabytes():
    from src.limits import max_audio_bytes

    assert max_audio_bytes() == 30 * 1024 * 1024


def test_the_conversation_ceiling_comes_from_the_setting(client, monkeypatch):
    monkeypatch.setenv("SESSION_CHAR_LIMIT", "100")
    sid = client.post("/interpreter/sessions", json={}).json()["id"]

    assert client.put(f"/interpreter/sessions/{sid}/turns/t1", json=_turn("a" * 100, at=1)).status_code == 200
    r = client.put(f"/interpreter/sessions/{sid}/turns/t2", json=_turn("one more", at=2))

    assert r.status_code == 409
    # The sentence that did fit is untouched, and the refused one is simply not there.
    turns = client.get(f"/interpreter/sessions/{sid}").json()["turns"]
    assert [len(t["original"]) for t in turns] == [100]


def test_the_default_conversation_ceiling_is_twenty_thousand():
    from src.limits import session_char_limit

    assert session_char_limit() == 20_000


def test_the_translation_does_not_count_against_the_ceiling(client, monkeypatch):
    """Only what people said and typed fills a conversation up."""
    monkeypatch.setenv("SESSION_CHAR_LIMIT", "200")
    sid = client.post("/interpreter/sessions", json={}).json()["id"]

    for i in range(2):
        r = client.put(f"/interpreter/sessions/{sid}/turns/t{i}", json={
            **_turn("a" * 100, at=i), "translation": "b" * 500,
        })
        assert r.status_code == 200, r.text

    assert len(client.get(f"/interpreter/sessions/{sid}").json()["turns"]) == 2


def test_the_speech_ceiling_comes_from_the_setting():
    from src.limits import tts_max_chars_per_request

    assert tts_max_chars_per_request() == 400


def test_config_reports_the_ceilings_the_page_shows(client, monkeypatch):
    monkeypatch.setenv("SESSION_CHAR_LIMIT", "1234")
    monkeypatch.setenv("MAX_SESSIONS", "7")
    monkeypatch.setenv("MAX_AUDIO_BYTES", "4096")

    limits = client.get("/config").json()["limits"]

    assert limits == {"max_sessions": 7, "session_char_limit": 1234, "max_audio_bytes": 4096}
