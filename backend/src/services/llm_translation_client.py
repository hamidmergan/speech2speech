"""Translation through the chat model, one text per call."""

import random
import time

from loguru import logger
from openai import APIError, OpenAI, RateLimitError

from src.providers import request_timeout


_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds, exponential: 2, 4, 8 plus jitter

# Below this a cut-off text is not split any further, the model is then the problem.
_MIN_SPLIT_CHARS = 500
# Where a long text may be cut, and how much of the mark stays on the left side.
_SPLIT_MARKS = (("\n\n", 0), ("\n", 0), (". ", 1), (" ", 0))

# Thinking models need room per entry, being generous costs nothing.
_TOKENS_BASE = 4096
_TOKENS_PER_ITEM = 1500
_MAX_OUTPUT_TOKENS = 32768


def _split_in_half(text: str) -> tuple[str, str, str] | None:
    """Cuts at the mark closest to the middle, None when the text is too short to cut."""
    if len(text) < _MIN_SPLIT_CHARS:
        return None
    middle = len(text) // 2
    for mark, stays_left in _SPLIT_MARKS:
        places = [i for i in (text.rfind(mark, 0, middle), text.find(mark, middle)) if i > 0]
        if not places:
            continue
        i = min(places, key=lambda x: abs(x - middle))
        return text[:i + stays_left], mark[stays_left:], text[i + len(mark):]
    return None


_SYSTEM_PROMPT = (
    "You are a professional translator specializing in academic and university content.\n"
    "Translate the given text {instruction}.\n"
    "Rules:\n"
    "- Output ONLY the translated text, nothing else.\n"
    "- No explanations, no notes, no preamble, no commentary.\n"
    "- Use formal register appropriate for academic and educational materials.\n"
    "- Preserve all formatting, line breaks, whitespace, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a well-established translation exists in the target language.\n"
    "- NEVER translate URLs, domains, email addresses, or code snippets. Leave them exactly as they are.\n"
    "- If the text contains a token matching __GLOSSARY_<number>__, copy it into your output EXACTLY as it appears, character for character. Never translate, alter, or remove such a token.\n"
    "- Do not introduce dashes or semicolons that are not present in the source text. Prefer periods, commas, colons, exclamation marks, and question marks.\n"
    "- Maintain consistent terminology throughout the text.\n"
    "- Do not add, remove, or reorder any content.\n"
)

class LLMTranslationClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider: str = "openai_compat",
        sampling: dict | None = None,
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=request_timeout())
        self._model = model
        self._provider = provider
        # Sampling values from the caller, empty means the built-in value applies.
        self._sampling = dict(sampling or {})
        # The switch that turns a thinking model's thinking off, set by the caller.
        self._extra_body: dict = {}

    def sampling(self, standard: float) -> dict:
        """The given values when set, otherwise the built-in temperature."""
        values = getattr(self, "_sampling", None)
        return dict(values) if values else {"temperature": standard}

    @staticmethod
    def _max_tokens_for(user: str, item_count: int = 1) -> int:
        """Token budget from a base, the entry count and the length."""
        budget = _TOKENS_BASE + _TOKENS_PER_ITEM * max(1, item_count) + len(user) // 2
        return min(_MAX_OUTPUT_TOKENS, budget)

    def _completion_with_retry(
        self, system: str, user: str, max_tokens: int | None = None, item_count: int = 1
    ) -> tuple[str, str]:
        """One call with growing waits, returns content and finish reason."""
        last_exc: Exception | None = None
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    **self.sampling(0.1),
                    max_tokens=max_tokens or self._max_tokens_for(user, item_count),
                    extra_body=getattr(self, "_extra_body", None) or None,
                )
                choice = response.choices[0]
                return choice.message.content or "", getattr(choice, "finish_reason", "stop") or "stop"
            except RateLimitError as e:
                last_exc = e
                if attempt == _RETRY_ATTEMPTS - 1:
                    break
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("LLM 429 rate limit, retry {}/{} in {:.1f}s", attempt + 1, _RETRY_ATTEMPTS, delay)
                time.sleep(delay)
            except APIError as e:
                # 5xx and other transient API errors
                last_exc = e
                status = getattr(e, "status_code", None)
                if status is None or status < 500:
                    raise
                if attempt == _RETRY_ATTEMPTS - 1:
                    break
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("LLM {} error, retry {}/{} in {:.1f}s", status, attempt + 1, _RETRY_ATTEMPTS, delay)
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        if source_lang:
            instruction = f"from {source_lang} to {target_lang}"
        else:
            instruction = f"to {target_lang} (auto-detect source language)"

        system = _SYSTEM_PROMPT.format(instruction=instruction)
        translated, finish_reason = self._completion_with_retry(system, text)
        if finish_reason == "length":
            # A single text cannot be split, so give it more room.
            logger.warning(
                "Translation was cut off ({} characters), second attempt with {} tokens.",
                len(text), _MAX_OUTPUT_TOKENS,
            )
            translated, finish_reason = self._completion_with_retry(
                system, text, max_tokens=_MAX_OUTPUT_TOKENS
            )
        if finish_reason == "length":
            # Still cut off with the full budget, so halve the text and translate both parts.
            halves = _split_in_half(text)
            if halves is None:
                raise RuntimeError(
                    f"The translation was cut off ({len(text)} characters of source). "
                    "The text is too long for the configured model."
                )
            left, separator, right = halves
            logger.warning(
                "Translation was cut off ({} characters), splitting into {} and {}.",
                len(text), len(left), len(right),
            )
            return (
                self.translate_text(left, source_lang, target_lang)
                + separator
                + self.translate_text(right, source_lang, target_lang)
            )
        return translated
