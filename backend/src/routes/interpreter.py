"""The interpreter: single sentences, speech windows, speech output and the stored conversations."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from loguru import logger
from pydantic import BaseModel, Field

from src.features.interpreter import repository as repo
from src.features.interpreter import service
from src.i18n import LANGUAGE_NAMES, TRANSLATE_LANGUAGES, get_locale, t
from src.providers import (
    FeatureNotConfigured,
    make_translation_client,
    make_tts_client,
    resolve,
    tts_voice,
)
from src.services.translation import TranslationService
from src.utils.text import sanitize_pasted_text

router = APIRouter(tags=["interpreter"])

# A spoken sentence, not a document. The same ceiling everywhere, so a sentence
# that was stored can always be translated and read aloud as well.
MAX_CHARS = 4000
# A language code such as "EN-US", never a sentence.
MAX_LANG_CHARS = 16
# An id the page made up, long enough for a UUID and for a timestamp plus suffix.
MAX_ID_CHARS = 64
# SQLite stores an integer in eight bytes. A Python int has no such ceiling, and
# anything past this one would raise OverflowError in the middle of a write.
MAX_SQLITE_INT = 2**63 - 1

Side = Literal["left", "right"]


def id_path():
    """A bounded id in the URL. An id goes straight into the database."""
    return Path(min_length=1, max_length=MAX_ID_CHARS)


class Sentence(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    target_lang: str = Field(max_length=MAX_LANG_CHARS)


class SessionIn(BaseModel):
    left_lang: str = Field(default="DE", max_length=MAX_LANG_CHARS)
    right_lang: str = Field(default="EN-US", max_length=MAX_LANG_CHARS)
    left_name: str = Field(default="", max_length=80)
    right_name: str = Field(default="", max_length=80)


class SessionPatch(BaseModel):
    left_lang: str | None = Field(default=None, max_length=MAX_LANG_CHARS)
    right_lang: str | None = Field(default=None, max_length=MAX_LANG_CHARS)
    left_name: str | None = Field(default=None, max_length=80)
    right_name: str | None = Field(default=None, max_length=80)
    ended: bool | None = None


class TurnIn(BaseModel):
    side: Side
    source: Literal["spoken", "typed"] = "spoken"
    original: str = Field(max_length=MAX_CHARS)
    translation: str = Field(default="", max_length=MAX_CHARS)
    status: Literal["translating", "done", "failed"] = "done"
    edited: bool = False
    at: int = Field(ge=0, le=MAX_SQLITE_INT)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CHARS)
    lang: str = Field(max_length=MAX_LANG_CHARS)


def translate_text(body: Sentence, locale: str):
    """One sentence straight through the provider, no job."""
    if body.target_lang not in TRANSLATE_LANGUAGES:
        raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    text = sanitize_pasted_text(body.text)
    if not text:
        raise HTTPException(status_code=400, detail=t("interpreter.textEmpty", locale))
    try:
        client = make_translation_client(resolve("translation"))
    except FeatureNotConfigured as e:
        raise HTTPException(status_code=503, detail=t("interpreter.noProvider", locale)) from e
    return TranslationService(client), text


async def run_translation(body: Sentence, locale: str) -> dict:
    translation_service, text = translate_text(body, locale)
    target = LANGUAGE_NAMES.get(body.target_lang, body.target_lang)
    try:
        # The provider call blocks, so it runs beside the event loop.
        translated = await run_in_threadpool(translation_service.translate_text, text, "", target)
    except Exception as e:
        logger.warning("Interpreter translation failed: {}", e)
        raise HTTPException(status_code=502, detail=t("interpreter.failed", locale)) from e
    return {"text": translated, "target_lang": body.target_lang}


@router.post("/interpreter/translate")
async def translate_sentence(
    body: Sentence,
    locale: str = Depends(get_locale),
):
    return await run_translation(body, locale)


# The speech model takes a two-letter language code, anything else is ignored rather than passed on.
_LANGUAGE = re.compile(r"^[a-z]{2}$")


@router.post("/interpreter/transcribe")
async def transcribe_window(
    audio: UploadFile = File(...),
    language: str | None = Form(None, max_length=MAX_LANG_CHARS),
    locale: str = Depends(get_locale),
):
    lang = language.strip().lower() if language else None
    if lang and not _LANGUAGE.match(lang):
        lang = None
    return {"text": await service.transcribe_upload(audio, lang, locale)}


@router.post("/interpreter/speak")
async def speak_sentence(
    body: SpeakIn,
    locale: str = Depends(get_locale),
):
    """Reads one sentence aloud and answers with the audio itself."""
    if body.lang not in TRANSLATE_LANGUAGES:
        raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    text = sanitize_pasted_text(body.text)
    if not text:
        raise HTTPException(status_code=400, detail=t("interpreter.textEmpty", locale))
    try:
        client = make_tts_client(resolve("tts"))
    except FeatureNotConfigured as e:
        raise HTTPException(status_code=503, detail=t("interpreter.noTts", locale)) from e
    try:
        audio = await run_in_threadpool(
            client.synthesize, text, body.lang, voice_id=tts_voice(),
        )
    except Exception as e:
        logger.warning("Interpreter speech output failed: {}", e)
        raise HTTPException(status_code=502, detail=t("interpreter.ttsFailed", locale)) from e
    return Response(content=audio, media_type="audio/mpeg")


def _known(session_id: str, locale: str) -> dict:
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=t("interpreter.sessionUnknown", locale))
    return session


@router.post("/interpreter/sessions")
def create_session(
    body: SessionIn,
    locale: str = Depends(get_locale),
):
    for lang in (body.left_lang, body.right_lang):
        if lang not in TRANSLATE_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    session = repo.create_session(
        body.left_lang, body.right_lang, body.left_name, body.right_name,
    )
    return service.state(session)


@router.get("/interpreter/sessions")
def list_sessions():
    return {"sessions": [service.summary(row) for row in repo.list_sessions()]}


@router.get("/interpreter/sessions/{session_id}")
def get_session(
    session_id: str = id_path(),
    locale: str = Depends(get_locale),
):
    return service.state(_known(session_id, locale))


@router.patch("/interpreter/sessions/{session_id}")
def patch_session(
    body: SessionPatch,
    session_id: str = id_path(),
    locale: str = Depends(get_locale),
):
    session = _known(session_id, locale)
    fields = {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "ended"}
    for lang in (fields.get("left_lang"), fields.get("right_lang")):
        if lang is not None and lang not in TRANSLATE_LANGUAGES:
            raise HTTPException(status_code=400, detail=t("interpreter.badTarget", locale))
    if body.ended is not None:
        fields["ended_at"] = repo.now() if body.ended else None
    updated = repo.update_session(session["id"], **fields) if fields else session
    return service.state(updated or session)


@router.delete("/interpreter/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: str = id_path(),
    locale: str = Depends(get_locale),
):
    if not repo.delete_session(session_id):
        raise HTTPException(status_code=404, detail=t("interpreter.sessionUnknown", locale))


@router.put("/interpreter/sessions/{session_id}/turns/{turn_id}")
def put_turn(
    body: TurnIn,
    session_id: str = id_path(),
    turn_id: str = id_path(),
    locale: str = Depends(get_locale),
):
    session = _known(session_id, locale)
    return service.save_turn(session, {"id": turn_id, **body.model_dump()}, locale)
