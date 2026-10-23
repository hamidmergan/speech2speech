"""Speech output via an OpenAI compatible endpoint, the voice comes from the environment."""
from __future__ import annotations

from openai import OpenAI

from src.limits import tts_max_chars_per_request
from src.providers import request_timeout
from src.services.tts_number_words import spell_numbers

# From which share of the ceiling on a sentence end is looked for.
_SEARCH_FROM = 0.6

_SENTENCE_ENDS = (". ", "! ", "? ", ".\n", "!\n", "?\n")


def _resolve_chunk_limit() -> int:
    """Ceiling per request, set with TTS_MAX_CHARS_PER_REQUEST."""
    return tts_max_chars_per_request()


def _split_text(text: str, max_chars: int | None = None) -> list[str]:
    """Splits long text, preferably at sentence ends, otherwise at word boundaries."""
    limit = max_chars or _resolve_chunk_limit()
    if len(text) <= limit:
        return [text]

    search_from = max(1, int(limit * _SEARCH_FROM))
    chunks: list[str] = []
    remaining = text

    while len(remaining) > limit:
        split_at = -1
        for punct in _SENTENCE_ENDS:
            pos = remaining.rfind(punct, search_from, limit)
            if pos != -1:
                split_at = pos + len(punct)
                break
        if split_at == -1:
            # No sentence end in reach: split at the last word boundary.
            pos = remaining.rfind(" ", search_from, limit)
            if pos != -1:
                split_at = pos + 1
        if split_at == -1:
            split_at = limit  # a single word is longer than the limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]

    if remaining:
        chunks.append(remaining)

    return chunks


class OpenAICompatTTSClient:
    """Client for any OpenAI-compatible TTS endpoint (POST /v1/audio/speech)."""

    def __init__(self, base_url: str, model: str, api_key: str = "none"):
        url = base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        self._base_url = url
        self._model = model
        self._api_key = api_key or "none"
        self._client = OpenAI(api_key=self._api_key, base_url=url, timeout=request_timeout())

    def synthesize(
        self,
        text: str,
        language: str = "",
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> bytes:
        """Convert text to MP3 bytes."""
        chunks = _split_text(text)
        audio_parts: list[bytes] = []

        for chunk in chunks:
            audio_parts.append(
                self._synthesize_one(chunk, voice_id=voice_id, speed=speed, language=language)
            )

        return b"".join(audio_parts)

    def _synthesize_one(
        self,
        text: str,
        *,
        voice_id: str = "default",
        speed: float = 1.0,
        language: str = "",
    ) -> bytes:
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        # Digits would otherwise sound German, the voice guesses its language from the text.
        text = spell_numbers(text, language)
        if not voice_id or voice_id == "default":
            raise ValueError("voice_id must be set, see TTS_VOICE")
        voice = voice_id
        # No tempo goes out, a voice slowed down by the provider echoes.
        payload: dict = {
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        if self._model:
            payload["model"] = self._model
        try:
            response = self._client.audio.speech.create(**payload)
            audio = response.content
        except Exception as e:
            raise RuntimeError(f"Speech output error: {e}") from e
        if not audio:
            raise RuntimeError("The speech endpoint returned no audio.")
        return audio
