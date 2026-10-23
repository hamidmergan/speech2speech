"""The one password: without it the API is open, with it every route wants the cookie."""

import pytest
from fastapi.testclient import TestClient

from src import access


@pytest.fixture
def guarded(models, monkeypatch):
    """The same installation, now behind a password."""
    monkeypatch.setenv("ACCESS_PASSWORD", "open sesame")
    monkeypatch.setenv("SESSION_SECRET", "a-long-random-string")
    from src.app import app

    with TestClient(app) as test_client:
        yield test_client


def test_without_a_password_everything_answers(client):
    assert client.get("/access").json() == {"required": False, "authenticated": True}
    assert client.get("/interpreter/sessions").status_code == 200


def test_with_a_password_the_conversation_is_closed(guarded):
    assert guarded.get("/access").json() == {"required": True, "authenticated": False}
    r = guarded.get("/interpreter/sessions")
    assert r.status_code == 401
    assert r.json()["detail"], "the page shows this sentence over its password field"


def test_the_right_password_opens_it(guarded):
    r = guarded.post("/access/login", json={"password": "open sesame"})
    assert r.status_code == 200 and r.json() == {"required": True, "authenticated": True}
    assert access.COOKIE_NAME in guarded.cookies

    assert guarded.get("/access").json() == {"required": True, "authenticated": True}
    assert guarded.get("/interpreter/sessions").status_code == 200
    # And the conversation really works behind it.
    sid = guarded.post("/interpreter/sessions", json={}).json()["id"]
    assert guarded.get(f"/interpreter/sessions/{sid}").status_code == 200


def test_the_wrong_password_does_not(guarded):
    r = guarded.post("/access/login", json={"password": "open sesam"})
    assert r.status_code == 401
    assert access.COOKIE_NAME not in guarded.cookies
    assert guarded.get("/interpreter/sessions").status_code == 401


def test_logging_out_closes_it_again(guarded):
    guarded.post("/access/login", json={"password": "open sesame"})
    guarded.post("/access/logout")
    assert guarded.get("/interpreter/sessions").status_code == 401


def test_health_and_config_stay_open(guarded):
    assert guarded.get("/health").status_code == 200
    r = guarded.get("/config")
    assert r.status_code == 200
    assert r.json()["access_required"] is True


def test_a_made_up_cookie_is_refused(guarded):
    guarded.cookies.set(access.COOKIE_NAME, "99999999999.deadbeef")
    assert guarded.get("/interpreter/sessions").status_code == 401


def test_a_cookie_without_a_signature_is_refused(guarded):
    guarded.cookies.set(access.COOKIE_NAME, "99999999999")
    assert guarded.get("/interpreter/sessions").status_code == 401


def test_a_run_out_cookie_is_refused(monkeypatch):
    monkeypatch.setenv("ACCESS_PASSWORD", "open sesame")
    monkeypatch.setenv("SESSION_SECRET", "a-long-random-string")
    # A token written a year and a day ago has run out by now.
    import time
    old = access.make_token(now=time.time() - access.COOKIE_MAX_AGE - 1)
    assert access.token_valid(old) is False
    assert access.token_valid(access.make_token()) is True


def test_a_changed_password_signs_everybody_out(monkeypatch):
    """Without SESSION_SECRET the password keys the signature."""
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setenv("ACCESS_PASSWORD", "first")
    token = access.make_token()
    assert access.token_valid(token) is True

    monkeypatch.setenv("ACCESS_PASSWORD", "second")
    assert access.token_valid(token) is False


def test_a_changed_secret_signs_everybody_out(monkeypatch):
    monkeypatch.setenv("ACCESS_PASSWORD", "stays the same")
    monkeypatch.setenv("SESSION_SECRET", "first-secret")
    token = access.make_token()
    assert access.token_valid(token) is True

    monkeypatch.setenv("SESSION_SECRET", "second-secret")
    assert access.token_valid(token) is False


def test_logging_in_without_a_password_set_says_so(client):
    r = client.post("/access/login", json={"password": "anything"})
    assert r.status_code == 200 and r.json() == {"required": False, "authenticated": True}
