from __future__ import annotations

import abc
import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class LLMResult:
    def __init__(self, text: str, raw: Any | None = None, model: str | None = None):
        self.text = text
        self.raw = raw
        self.model = model

    def parse_json(self) -> dict[str, Any] | None:
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, TypeError):
            return None


class LLMProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        timeout: int | None = None,
    ) -> LLMResult:
        raise NotImplementedError

    @classmethod
    def create(cls) -> "LLMProvider":
        provider = settings.llm_provider.lower()
        if provider in ("openai", "groq"):
            return OpenAIProvider()
        if provider == "mock":
            return MockLLMProvider()
        return NoopLLMProvider()


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY required for openai/groq provider")
        self.is_groq = settings.llm_provider.lower() == "groq"
        if self.is_groq:
            self.name = "groq"
            self.base_url = settings.llm_base_url or "https://api.groq.com/openai/v1"
        else:
            self.base_url = settings.llm_base_url or None

    def _resolve_model(self, model: str | None) -> str:
        chosen = model or settings.judge_model
        if self.is_groq and (not chosen or chosen.startswith("gpt-4") or "llama" in chosen):
            return "openai/gpt-oss-120b"
        return chosen

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        timeout: int | None = None,
    ) -> LLMResult:
        import openai

        target_model = self._resolve_model(model)
        client = openai.AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=self.base_url,
            timeout=timeout or settings.request_timeout,
        )
        try:
            chat = await client.chat.completions.create(
                model=target_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            text = chat.choices[0].message.content or ""
            return LLMResult(text=text, raw=chat, model=target_model)
        except openai.APIError:
            raise
        finally:
            await client.close()


class MockLLMProvider(LLMProvider):
    """Deterministic fake used for tests and development (never used for real judging)."""

    name = "mock"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        timeout: int | None = None,
    ) -> LLMResult:
        return LLMResult(
            text=json.dumps(
                {
                    "classification": "BLOCKED",
                    "confidence": 0.5,
                    "evidence": "mock judge: no evidence",
                    "reasoning_summary": "mock provider",
                    "impact": "none",
                    "violated_boundary": "none",
                }
            ),
            model="mock",
        )


class NoopLLMProvider(LLMProvider):
    """Used when LLM judging is disabled."""

    name = "none"

    def __init__(self) -> None:
        logger.warning("LLM provider is 'none'; LLM judge and generator will be skipped")

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        timeout: int | None = None,
    ) -> LLMResult:
        raise RuntimeError("LLM provider is not configured")


EMBEDDING_CACHE: dict[str, list[float]] = {}


class EmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @classmethod
    def create(cls) -> "EmbeddingProvider | None":
        provider = settings.embedding_provider.lower()
        if provider in ("", "none"):
            return None
        if provider == "sentence-transformers":
            return SentenceTransformerProvider()
        if provider == "openai":
            return OpenAIBackendEmbeddingProvider()
        return None


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers not installed; set EMBEDDING_PROVIDER=none"
            ) from exc
        self._model = SentenceTransformer(settings.embedding_model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if t not in EMBEDDING_CACHE]
        if missing:
            vectors = self._model.encode(missing, show_progress_bar=False).tolist()
            for t, v in zip(missing, vectors):
                EMBEDDING_CACHE[t] = v
        return [EMBEDDING_CACHE[t] for t in texts]


class OpenAIBackendEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY required for openai embeddings")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import openai

        client = openai.AsyncOpenAI(
            api_key=settings.llm_api_key, base_url=settings.llm_base_url or None
        )
        try:
            result = await client.embeddings.create(
                model=settings.embedding_model, input=texts
            )
            return [d.embedding for d in result.data]
        finally:
            await client.close()


def get_llm_provider() -> LLMProvider:
    return LLMProvider.create()


def get_embedding_provider() -> EmbeddingProvider | None:
    return EmbeddingProvider.create()