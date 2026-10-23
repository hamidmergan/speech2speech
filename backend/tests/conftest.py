"""A fake OpenAI compatible server, so no test needs a real model.

The same server answers all three endpoints the app calls: chat completions for
the translation, audio transcriptions for the microphone and audio speech for the
reading aloud. Every request is recorded, so a test can assert what actually went
out as well as what came back.
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

# A real MP3 frame header, enough for a test to recognise the audio it got back.
MP3_PREFIX = b"\xff\xfb\x90\x64"


def multipart_field(body: bytes, name: str):
    """One plain field out of a multipart body, None when it is not in there."""
    match = re.search(rb'name="' + name.encode() + rb'"\r\n\r\n(.*?)\r\n--', body, re.S)
    return match.group(1).decode() if match else None


class FakeServer:
    def __init__(self):
        self.chat_requests: list[dict] = []
        self.transcribe_requests: list[dict] = []
        self.speech_requests: list[dict] = []
        # Paths that answer with an error instead, for example "/v1/chat/completions".
        self.fail_paths: set[str] = set()
        self.fail_status = 500
        # The reply the chat endpoint gives. The default echoes the target language.
        self.chat_reply = None
        self.chat_finish_reason = "stop"
        # What the transcription endpoint says it heard, wrapped as a JSON object the
        # way a short clip comes back from several servers.
        self.heard = '{"text": "Hallo Welt"}'
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status: int, data: bytes, content_type: str):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _json(self, status: int, payload) -> None:
                self._send(status, json.dumps(payload).encode(), "application/json")

            def do_GET(self):
                if self.path.endswith("/models"):
                    self._json(200, {"object": "list", "data": []})
                    return
                self._json(404, {"error": {"message": "unknown path"}})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                path = self.path
                if path in outer.fail_paths:
                    self._json(outer.fail_status, {"error": {"message": "no"}})
                    return
                if path.endswith("/chat/completions"):
                    outer._chat(self, body)
                elif path.endswith("/audio/transcriptions"):
                    outer._transcribe(self, body)
                elif path.endswith("/audio/speech"):
                    outer._speech(self, body)
                else:
                    self._json(404, {"error": {"message": "unknown path"}})

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    # ─── the three endpoints ────────────────────────────────────────────────

    def _chat(self, handler, body: bytes) -> None:
        payload = json.loads(body)
        with self.lock:
            self.chat_requests.append(payload)
        system = payload["messages"][0]["content"]
        user = payload["messages"][1]["content"]
        # The prompt names the target language, so the answer can show which one arrived.
        target = system.split(" to ")[-1].split(".")[0].split(" (")[0].strip()
        text = self.chat_reply if self.chat_reply is not None else f"[{target}] {user}"
        handler._json(200, {
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": payload["model"],
            "choices": [{
                "index": 0,
                "finish_reason": self.chat_finish_reason,
                "message": {"role": "assistant", "content": text},
            }],
        })

    def _transcribe(self, handler, body: bytes) -> None:
        with self.lock:
            self.transcribe_requests.append({
                "model": multipart_field(body, "model"),
                "language": multipart_field(body, "language"),
                "response_format": multipart_field(body, "response_format"),
                "size": len(body),
            })
        handler._send(200, self.heard.encode(), "text/plain")

    def _speech(self, handler, body: bytes) -> None:
        payload = json.loads(body)
        with self.lock:
            self.speech_requests.append(payload)
        if payload.get("voice") != "alloy":
            # Several servers know one voice only and answer 400 on any other name.
            handler._json(400, {"error": {"message": "unknown voice"}})
            return
        # One frame per ten characters, so a test sees that long text came back longer.
        audio = MP3_PREFIX + bytes(len(payload["input"]) % 256 for _ in range(1))
        audio += MP3_PREFIX * (1 + len(payload["input"]) // 10)
        handler._send(200, audio, "audio/mpeg")

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.httpd.server_port}/v1"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = FakeServer()
    yield s
    s.stop()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """No model, no password and a database of its own for every test."""
    import os

    for name in list(os.environ):
        if name.split("_")[0] in {"LLM", "STT", "TTS"} or name in {
            "OPENAI_API_KEY", "ACCESS_PASSWORD", "SESSION_SECRET", "MAX_SESSIONS",
            "SESSION_CHAR_LIMIT", "MAX_AUDIO_BYTES", "TTS_MAX_CHARS_PER_REQUEST",
        }:
            monkeypatch.delenv(name)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    from src import database
    database.reset_for_tests()
    yield
    database.reset_for_tests()


@pytest.fixture
def models(server, monkeypatch):
    """All three capabilities pointed at the fake server."""
    monkeypatch.setenv("LLM_BASE_URL", server.base_url)
    monkeypatch.setenv("LLM_MODEL", "chat-test")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("STT_MODEL", "stt-test")
    monkeypatch.setenv("TTS_MODEL", "tts-test")
    monkeypatch.setenv("TTS_VOICE", "alloy")
    return server


@pytest.fixture
def client(models):
    """A test client with every model configured and the schema in place."""
    from fastapi.testclient import TestClient
    from src.app import app

    with TestClient(app) as test_client:
        yield test_client
