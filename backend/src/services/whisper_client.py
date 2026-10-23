"""Speech to text through an OpenAI compatible /audio/transcriptions endpoint.

The interpreter sends short windows while somebody is still speaking, so there is
no chunking and no retry here. A failed window is simply sent again by the page
with the next window.
"""

import json

from openai import OpenAI

from src.providers import request_timeout


def clean_whisper_response(raw: str) -> str:
    """Clean a response that may be JSON-encoded (wrapped in quotes with escaped newlines)."""
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            text = text[1:-1]
            text = text.replace("\\n", "\n").replace("\\r", "\r")
    return text.strip()


class WhisperClient:
    """Client for any OpenAI compatible speech to text endpoint."""

    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "openai_compat"):
        self._client = OpenAI(api_key=api_key or "none", base_url=base_url, timeout=request_timeout())
        self._model = model
        self._provider = provider

    def transcribe(self, file_path: str, response_format: str = "text", language: str | None = None) -> str:
        """Transcribe audio in its original language, the language is optional."""
        extra = {"language": language} if language else {}
        try:
            with open(file_path, "rb") as f:
                result = str(self._client.audio.transcriptions.create(
                    model=self._model,
                    file=f,
                    response_format=response_format,
                    **extra,
                ))
            if not result:
                raise RuntimeError("The speech model returned no output")
            return clean_whisper_response(result)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Speech to text error ({self._provider}): {e}") from e
