"""Reading a translation aloud: the audio itself comes back, or a sentence saying why not."""

from fastapi.testclient import TestClient

from tests.conftest import MP3_PREFIX


def test_a_sentence_comes_back_as_audio(client, models):
    r = client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/mpeg"
    # Not merely a response: real audio bytes arrived.
    assert r.content.startswith(MP3_PREFIX)
    assert len(r.content) > len(MP3_PREFIX)
    assert models.speech_requests[0]["input"] == "Guten Tag"
    assert models.speech_requests[0]["model"] == "tts-test"
    assert models.speech_requests[0]["response_format"] == "mp3"


def test_the_voice_comes_from_the_setting(client, models):
    client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})
    assert models.speech_requests[0]["voice"] == "alloy"


def test_a_voice_the_server_does_not_know_answers_502(client, models, monkeypatch):
    """Several speech servers know one voice only and answer 400 on any other name."""
    monkeypatch.setenv("TTS_VOICE", "nova")
    r = client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})
    assert r.status_code == 502
    assert models.speech_requests[0]["voice"] == "nova"


def test_long_text_is_split_and_comes_back_as_one_file(client, models, monkeypatch):
    """Past the per request ceiling the text is split, and every part is in the answer."""
    monkeypatch.setenv("TTS_MAX_CHARS_PER_REQUEST", "120")
    text = "Bitte gehen Sie den Gang hinunter. " * 20
    assert len(text) > 600

    r = client.post("/interpreter/speak", json={"text": text, "lang": "DE"})

    assert r.status_code == 200, r.text
    assert len(models.speech_requests) > 1, "one request per part"
    # Nothing was dropped on the way: every part of the text went out.
    sent = "".join(req["input"] for req in models.speech_requests)
    assert sent.replace(" ", "") == text.strip().replace(" ", "")
    # And the audio of every part is in the one file that comes back.
    assert r.content.count(MP3_PREFIX) > len(models.speech_requests)


def test_digits_are_spelled_out_for_english(client, models):
    """A voice guesses its language from the text, so bare digits would sound German."""
    client.post("/interpreter/speak", json={"text": "Room 12 on floor 3", "lang": "EN-US"})
    assert models.speech_requests[0]["input"] == "Room twelve on floor three"


def test_german_text_keeps_its_digits(client, models):
    client.post("/interpreter/speak", json={"text": "Raum 12 im 3. Stock", "lang": "DE"})
    assert models.speech_requests[0]["input"] == "Raum 12 im 3. Stock"


def test_without_a_speech_model_it_answers_503(client, monkeypatch):
    monkeypatch.delenv("TTS_MODEL")
    r = client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})
    assert r.status_code == 503


def test_a_failing_speech_model_answers_502(client, models):
    models.fail_paths.add("/v1/audio/speech")
    r = client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})
    assert r.status_code == 502


def test_an_unknown_language_is_refused(client):
    assert client.post("/interpreter/speak", json={"text": "Bonjour", "lang": "FR"}).status_code == 400


def test_empty_text_is_refused(client, models):
    assert client.post("/interpreter/speak", json={"text": "   ", "lang": "DE"}).status_code == 400
    assert models.speech_requests == []


def test_the_speech_endpoint_may_sit_somewhere_else(server, monkeypatch):
    """TTS_BASE_URL overrides, the key falls back to the chat values."""
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("LLM_MODEL", "chat-test")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("TTS_MODEL", "tts-test")
    monkeypatch.setenv("TTS_BASE_URL", server.base_url)
    monkeypatch.setenv("TTS_VOICE", "alloy")
    from src.app import app

    with TestClient(app) as test_client:
        r = test_client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})

    assert r.status_code == 200, r.text
    assert r.content.startswith(MP3_PREFIX)


def test_a_base_url_without_v1_still_finds_the_endpoint(server, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", server.base_url.removesuffix("/v1"))
    monkeypatch.setenv("LLM_MODEL", "chat-test")
    monkeypatch.setenv("TTS_MODEL", "tts-test")
    monkeypatch.setenv("TTS_VOICE", "alloy")
    from src.app import app

    with TestClient(app) as test_client:
        r = test_client.post("/interpreter/speak", json={"text": "Guten Tag", "lang": "DE"})

    assert r.status_code == 200, r.text
    assert r.content.startswith(MP3_PREFIX)
