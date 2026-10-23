"""Digits to words before the text goes to the voicing."""

import re

from loguru import logger

# Digit sequence with thousands separators and a decimal, standing alone as a word.
_NUMBER = re.compile(r"(?<![\w.,/@-])(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:\.\d+)?)(?![\w/@-])")

# Addresses stay untouched, a digit there is not a spoken number.
_ADDRESS = re.compile(r"\S+(?:://|@)\S+|\b\S+\.(?:de|com|org|net|eu|io)\b", re.I)

# Four-digit numbers in this range are spoken as a year.
_YEAR_FROM, _YEAR_TO = 1500, 2099

# Only for these languages was the voice's guessing measured, elsewhere nothing changes.
_MEASURED_LANGUAGES = {"en"}


def _language_code(language: str) -> str:
    """'EN-US' becomes 'en'."""
    return (language or "").strip().replace("_", "-").split("-")[0].lower()


def _as_word(raw: str, lang: str) -> str:
    from num2words import num2words

    text = raw.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw) else raw
    text = text.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw) else text
    number = float(text) if "." in text else int(text)
    if isinstance(number, int) and _YEAR_FROM <= number <= _YEAR_TO and len(raw) == 4:
        return num2words(number, lang=lang, to="year")
    return num2words(number, lang=lang)


def spell_numbers(text: str, language: str) -> str:
    """Spells digits out as words, English only."""
    if not text:
        return ""
    lang = _language_code(language)
    if lang not in _MEASURED_LANGUAGES:
        return text
    try:
        from num2words import CONVERTER_CLASSES
    except ImportError:
        logger.warning("num2words is missing, digits go to the voicing unchanged")
        return text
    if lang not in CONVERTER_CLASSES:
        return text

    protected = [(m.start(), m.end()) for m in _ADDRESS.finditer(text)]

    def replace_one(match: re.Match) -> str:
        if any(a <= match.start() < b for a, b in protected):
            return match.group(0)
        try:
            return _as_word(match.group(0), lang)
        except Exception:  # noqa: BLE001 - a number that cannot be read stays as it is
            return match.group(0)

    return _NUMBER.sub(replace_one, text)
