"""What the page asks before it draws anything."""

from fastapi import APIRouter

from src import access, providers
from src.limits import max_audio_bytes, max_sessions, session_char_limit

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
def config() -> dict:
    """Which model kinds this installation has, and the ceilings the page shows."""
    models = providers.configured()
    return {
        "stt": models["stt"],
        "tts": models["tts"],
        "translation": models["llm"],
        "access_required": access.required(),
        "limits": {
            "max_sessions": max_sessions(),
            "session_char_limit": session_char_limit(),
            "max_audio_bytes": max_audio_bytes(),
        },
    }
