"""The provider layer: every model comes from the environment.

One OpenAI compatible endpoint per capability. The chat model is mandatory, it
does the translating. Speech to text and speech output are optional: when their
model is missing the matching route answers 503 and ``GET /config`` reports the
capability as off.

Variables, per capability ``<PREFIX>_BASE_URL``, ``<PREFIX>_MODEL`` and
``<PREFIX>_API_KEY``:

====================  ========  =================================================
Capability            Prefix    Purpose
====================  ========  =================================================
chat, translation     LLM       translates what was said or typed
speech to text        STT       writes down what the microphone heard
speech output         TTS       reads a translation aloud
====================  ========  =================================================

Base URL and API key fall back to the ``LLM_*`` values, the model never does.
A missing API key becomes the placeholder ``none``, the OpenAI library needs a
value even where the server wants none.

Speech output additionally wants ``TTS_VOICE``. Voice names differ from server to
server and most self hosted ones answer 400 on a name they do not know, so a
guessed default would show a read aloud button that fails on every press.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

# A capability and the environment prefix behind it.
CAPABILITIES: tuple[str, ...] = ("llm", "stt", "tts")

# Which capability serves a feature. The features are the names the routes ask for.
FEATURE_CAPABILITY: dict[str, str] = {
    "translation": "llm",
    "stt": "stt",
    "tts": "tts",
}

# Readable names in logs.
_NAME: dict[str, str] = {
    "llm": "chat model",
    "stt": "speech to text model",
    "tts": "speech model",
}

# Only the chat model has to be there, the others switch a feature off when missing.
REQUIRED: frozenset[str] = frozenset({"llm"})

# Connect, write and pool guard. The read timeout is the long one.
_CONNECT_TIMEOUT_SECONDS = 10.0
# A gateway usually gives up on a request after 60 s, so waiting five minutes only burns a slot.
_READ_TIMEOUT_SECONDS = 90.0


class FeatureNotConfigured(RuntimeError):
    """No model is set up for this feature."""


@dataclass
class FeatureBinding:
    """One feature, the endpoint behind it and the model it calls."""

    feature: str
    provider: dict
    model: Optional[str]

    @property
    def protocol(self) -> str:
        return "openai_compat"


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def ensure_v1(base_url: str) -> str:
    """An OpenAI compatible base URL always ends in /v1."""
    url = (base_url or "").rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def request_timeout(read_seconds: float = _READ_TIMEOUT_SECONDS):
    """A short connect guard with a long read timeout.

    openai re-exports the Timeout class of the HTTP library it ships with, so the
    right class comes from openai itself instead of a guessed module name. A plain
    number would set all four fields at once and stretch the connect guard to the
    read timeout.
    """
    from openai import Timeout

    return Timeout(
        connect=_CONNECT_TIMEOUT_SECONDS,
        read=read_seconds,
        write=_CONNECT_TIMEOUT_SECONDS,
        pool=_CONNECT_TIMEOUT_SECONDS,
    )


def _cap_of(feature: str) -> str:
    capability = FEATURE_CAPABILITY.get(feature)
    if capability is None:
        raise FeatureNotConfigured(f"unknown feature {feature!r}")
    return capability


def provider_for(capability: str) -> Optional[dict]:
    """The endpoint of a capability, or None when its model is not set."""
    prefix = capability.upper()
    model = _env(f"{prefix}_MODEL")
    if not model:
        return None
    base_url = _env(f"{prefix}_BASE_URL") or _env("LLM_BASE_URL")
    if not base_url:
        return None
    if capability == "tts" and not _env("TTS_VOICE"):
        # No voice, no speech output. Guessing one would mean a button that
        # answers 502 on every press with nothing naming the real cause.
        return None
    api_key = (
        _env(f"{prefix}_API_KEY")
        or _env("LLM_API_KEY")
        or _env("OPENAI_API_KEY")
        # The OpenAI library insists on a value, a self hosted server ignores it.
        or "none"
    )
    return {
        "name": _NAME[capability],
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "protocol": "openai_compat",
    }


def missing_reason(capability: str) -> str:
    """What the operator has to set, named by its variable."""
    prefix = capability.upper()
    if not _env(f"{prefix}_MODEL"):
        return f"{prefix}_MODEL is not set"
    if not (_env(f"{prefix}_BASE_URL") or _env("LLM_BASE_URL")):
        return f"{prefix}_BASE_URL is not set and LLM_BASE_URL has no value to fall back to"
    return f"{prefix}_VOICE is not set"


def resolve(feature: str) -> FeatureBinding:
    """The binding for a feature, or FeatureNotConfigured when its model is missing."""
    capability = _cap_of(feature)
    provider = provider_for(capability)
    if provider is None:
        raise FeatureNotConfigured(
            f"No model is configured for '{feature}': {missing_reason(capability)}."
        )
    return FeatureBinding(feature=feature, provider=provider, model=provider["model"])


def is_configured(feature: str) -> bool:
    """Whether this feature has a model, without raising."""
    try:
        return provider_for(_cap_of(feature)) is not None
    except FeatureNotConfigured:
        return False


def configured() -> dict:
    """What ``GET /config`` reports: which model kinds this installation has."""
    return {name: provider_for(name) is not None for name in CAPABILITIES}


def check_required() -> list[str]:
    """The missing mandatory models, empty when the installation can start working."""
    return [
        f"{name.upper()}: {missing_reason(name)}"
        for name in sorted(REQUIRED)
        if provider_for(name) is None
    ]


def tts_voice() -> str:
    """The voice the speech endpoint is asked for, from TTS_VOICE.

    No default. Named voices differ from server to server, so a guessed one would
    be refused by most of them.
    """
    return _env("TTS_VOICE")


# ─── The factories turn a binding into a finished client ────────────────────


# A client owns an HTTP connection pool. One per endpoint instead of one per
# request, otherwise live translation opens a new TCP (and TLS) handshake about
# once a second. The settings are the key, so a changed variable gives a new one.
_CLIENT_CACHE_SIZE = 8


@lru_cache(maxsize=_CLIENT_CACHE_SIZE)
def _translation_client(api_key: str, base_url: str, model: str, name: str):
    from src.services.llm_translation_client import LLMTranslationClient

    return LLMTranslationClient(api_key=api_key, base_url=base_url, model=model, provider=name)


@lru_cache(maxsize=_CLIENT_CACHE_SIZE)
def _whisper_client(api_key: str, base_url: str, model: str, name: str):
    from src.services.whisper_client import WhisperClient

    return WhisperClient(api_key=api_key, base_url=base_url, model=model, provider=name)


@lru_cache(maxsize=_CLIENT_CACHE_SIZE)
def _tts_client(api_key: str, base_url: str, model: str):
    from src.services.openai_compat_tts import OpenAICompatTTSClient

    return OpenAICompatTTSClient(base_url=base_url, model=model, api_key=api_key)


def forget_clients() -> None:
    """Drops the cached clients. The tests point the same settings at a new server."""
    _translation_client.cache_clear()
    _whisper_client.cache_clear()
    _tts_client.cache_clear()


def make_translation_client(binding: FeatureBinding):
    """An LLMTranslationClient for the chat model."""
    provider = binding.provider
    return _translation_client(
        provider.get("api_key") or "none",
        ensure_v1(provider["base_url"]),
        binding.model or "",
        provider["name"],
    )


def make_whisper_client(binding: FeatureBinding):
    """A client for speech recognition, the model is mandatory here."""
    if not binding.model:
        raise FeatureNotConfigured("STT_MODEL is not set")
    provider = binding.provider
    return _whisper_client(
        provider.get("api_key") or "none",
        ensure_v1(provider["base_url"]),
        binding.model,
        provider["name"],
    )


def make_tts_client(binding: FeatureBinding):
    """An OpenAICompatTTSClient for the configured speech endpoint."""
    if not binding.model:
        raise FeatureNotConfigured("TTS_MODEL is not set")
    provider = binding.provider
    return _tts_client(
        provider.get("api_key") or "none",
        provider["base_url"],
        binding.model,
    )
