"""Text fragments of the backend, the language comes from the request header."""

from fastapi import Header, Query

SUPPORTED_LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"

# The two languages a conversation runs in. The codes are the ones the page sends.
TRANSLATE_LANGUAGES: tuple[str, ...] = (
    "DE", "EN-US",
)

# The language name the chat model is asked to translate into.
LANGUAGE_NAMES: dict[str, str] = {
    "DE": "German",
    "EN-US": "English",
}


# All visible texts of the backend, always add them in both languages.
MESSAGES: dict[str, dict[str, str]] = {
    "interpreter.badTarget": {
        "de": "Diese Sprache kennt der Dolmetscher nicht.",
        "en": "The interpreter does not know this language.",
    },
    "interpreter.noProvider": {
        "de": "Kein Übersetzungsanbieter eingerichtet.",
        "en": "No translation provider is configured.",
    },
    "interpreter.ended": {
        "de": "Das Gespräch ist beendet.",
        "en": "The conversation has ended.",
    },
    "interpreter.full": {
        "de": "Das Gespräch ist voll. Starte ein neues Gespräch.",
        "en": "This conversation is full. Start a new one.",
    },
    "interpreter.sessionUnknown": {
        "de": "Dieses Gespräch gibt es nicht.",
        "en": "This conversation does not exist.",
    },
    "interpreter.audioTooLarge": {
        "de": "Die Aufnahme ist zu groß. Nimm kürzer auf, es wird nichts abgeschnitten.",
        "en": "The recording is too large. Record a shorter one, nothing is cut away.",
    },
    "interpreter.noStt": {
        "de": "Kein Anbieter für Spracherkennung eingerichtet.",
        "en": "No speech recognition provider is configured.",
    },
    "interpreter.sttFailed": {
        "de": "Die Spracherkennung ist gerade nicht möglich.",
        "en": "Speech recognition is not available right now.",
    },
    "interpreter.failed": {
        "de": "Die Übersetzung ist gerade nicht möglich.",
        "en": "Translation is not available right now.",
    },
    "interpreter.noTts": {
        "de": "Kein Anbieter für Sprachausgabe eingerichtet.",
        "en": "No speech output provider is configured.",
    },
    "interpreter.ttsFailed": {
        "de": "Das Vorlesen ist gerade nicht möglich.",
        "en": "Reading aloud is not available right now.",
    },
    "interpreter.textEmpty": {
        "de": "Kein Text übergeben.",
        "en": "No text was given.",
    },
    "access.wrongPassword": {
        "de": "Das Passwort stimmt nicht.",
        "en": "That password is not right.",
    },
    "access.needed": {
        "de": "Bitte das Zugangspasswort eingeben.",
        "en": "Please enter the access password.",
    },
}


def parse_accept_language(header: str | None) -> str:
    """Return the first supported locale from Accept-Language, or DEFAULT_LOCALE."""
    if not header:
        return DEFAULT_LOCALE
    for raw in header.split(","):
        tag = raw.strip().split(";")[0].lower()
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE


async def get_locale(
    accept_language: str | None = Header(default=None),
    lang: str | None = Query(default=None),
) -> str:
    """FastAPI dependency: resolve the locale from `?lang=` or Accept-Language."""
    if lang and lang in SUPPORTED_LOCALES:
        return lang
    return parse_accept_language(accept_language)


def t(key: str, locale: str = DEFAULT_LOCALE, **params: object) -> str:
    """Translate a message key. Falls back to the default locale, then to the key itself."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(locale) or entry.get(DEFAULT_LOCALE) or key
    return text.format(**params) if params else text
