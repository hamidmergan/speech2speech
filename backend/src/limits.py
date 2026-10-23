"""The ceilings of this installation, every one of them settable in the environment.

None of them cuts anything away. A recording over MAX_AUDIO_BYTES is refused with
a message, and a conversation that reaches SESSION_CHAR_LIMIT ends and stays
readable instead of losing its oldest sentences.
"""

import os

# How many conversations stay at once, the one untouched longest drops out.
MAX_SESSIONS_DEFAULT = 100
# What a conversation may collect, spoken and typed together, roughly an hour of back and forth.
SESSION_CHAR_LIMIT_DEFAULT = 20_000
# Largest recording one request may carry.
MAX_AUDIO_BYTES_DEFAULT = 30 * 1024 * 1024
# Characters per request to the speech model, longer text is split at sentence ends.
TTS_MAX_CHARS_PER_REQUEST_DEFAULT = 400


def _positive_int(name: str, default: int) -> int:
    """The value from the environment, or the default when it is missing or not a positive number."""
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def max_sessions() -> int:
    return _positive_int("MAX_SESSIONS", MAX_SESSIONS_DEFAULT)


def session_char_limit() -> int:
    return _positive_int("SESSION_CHAR_LIMIT", SESSION_CHAR_LIMIT_DEFAULT)


def max_audio_bytes() -> int:
    return _positive_int("MAX_AUDIO_BYTES", MAX_AUDIO_BYTES_DEFAULT)


def tts_max_chars_per_request() -> int:
    return _positive_int("TTS_MAX_CHARS_PER_REQUEST", TTS_MAX_CHARS_PER_REQUEST_DEFAULT)
