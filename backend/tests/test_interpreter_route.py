"""The interpreter translates single sentences straight away and never creates a job."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_without_models(monkeypatch):
    from src.app import app

    with TestClient(app) as test_client:
        yield test_client


def test_translates_one_sentence(client, models):
    r = client.post("/interpreter/translate", json={"text": "Wo ist die Mensa?", "target_lang": "EN-US"})

    assert r.status_code == 200, r.text
    # The translation itself comes back, not only a confirmation that something happened.
    assert r.json() == {"text": "[English] Wo ist die Mensa?", "target_lang": "EN-US"}
    # The code the page sends reaches the model as a language name.
    assert "to English" in models.chat_requests[0]["messages"][0]["content"]
    assert models.chat_requests[0]["messages"][1]["content"] == "Wo ist die Mensa?"
    assert models.chat_requests[0]["model"] == "chat-test"


def test_translates_into_german_too(client, models):
    r = client.post("/interpreter/translate", json={"text": "Where is the canteen?", "target_lang": "DE"})

    assert r.status_code == 200, r.text
    assert r.json()["text"] == "[German] Where is the canteen?"


def test_unknown_language_is_refused(client):
    r = client.post("/interpreter/translate", json={"text": "Hallo", "target_lang": "FR"})
    assert r.status_code == 400


def test_empty_text_is_refused(client):
    r = client.post("/interpreter/translate", json={"text": "   ", "target_lang": "DE"})
    assert r.status_code == 400


def test_without_a_provider_it_answers_503(client_without_models):
    r = client_without_models.post("/interpreter/translate", json={"text": "Hallo", "target_lang": "EN-US"})
    assert r.status_code == 503
    assert "LLM_MODEL" not in r.json()["detail"], "the sentence is for a person, the variable goes to the log"


def test_a_failing_model_answers_502(client, models):
    models.fail_paths.add("/v1/chat/completions")
    r = client.post("/interpreter/translate", json={"text": "Hallo", "target_lang": "EN-US"})
    assert r.status_code == 502


def test_a_long_sentence_still_goes_through_whole(client, models):
    """A spoken sentence may run to the cap, and all of it has to reach the model."""
    text = "Ich erklaere Ihnen jetzt den Weg zum Pruefungsamt. " * 78
    assert 3900 < len(text) <= 4000, "a sentence right at the cap, not a short one"

    r = client.post("/interpreter/translate", json={"text": text, "target_lang": "EN-US"})

    assert r.status_code == 200, r.text
    assert models.chat_requests[0]["messages"][1]["content"] == text.strip()
    assert r.json()["text"].endswith(text.strip())


def test_a_sentence_past_the_cap_is_refused_not_cut(client, models):
    r = client.post("/interpreter/translate", json={"text": "a" * 4001, "target_lang": "EN-US"})

    assert r.status_code == 422
    assert models.chat_requests == [], "nothing is sent on half"


def test_a_sentence_that_can_be_stored_can_also_be_translated(client, models):
    """The store took 4000 characters while translate stopped at 2000, so a long
    spoken turn was saved and then never translatable."""
    text = "Guten Tag und herzlich willkommen bei uns im Haus. " * 59
    assert 2000 < len(text) <= 4000

    sid = client.post("/interpreter/sessions", json={}).json()["id"]
    stored = client.put(
        f"/interpreter/sessions/{sid}/turns/t1",
        json={"side": "left", "source": "spoken", "original": text,
              "translation": "", "status": "done", "edited": False, "at": 1000},
    )
    assert stored.status_code == 200, stored.text
    assert stored.json()["original"] == text

    r = client.post("/interpreter/translate", json={"text": text, "target_lang": "EN-US"})
    assert r.status_code == 200, r.text
    assert models.chat_requests[-1]["messages"][1]["content"] == text.strip()
