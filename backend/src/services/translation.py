"""The thin layer the routes talk to, so the client behind it can be swapped."""

from src.services.llm_translation_client import LLMTranslationClient


class TranslationService:
    def __init__(self, client: LLMTranslationClient):
        self._client = client

    @property
    def client(self) -> LLMTranslationClient:
        return self._client

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            return text
        return self._client.translate_text(text, source_lang, target_lang)
