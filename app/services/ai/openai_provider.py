"""OpenAI-backed implementation of LLMProvider / EmbeddingProvider / VisionProvider.

This is the fully-functional reference implementation: one API surface
covers structured chat completions (content analysis + search parsing),
vision, and embeddings. `base_url` can be overridden to point at any
OpenAI-compatible endpoint (Azure OpenAI, local vLLM, etc.) without code
changes.
"""

from __future__ import annotations

import base64

import httpx
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.content import ContentAnalysis, ContentMetadata, SearchFilter
from app.services.ai.base import AIProviderError
from app.services.ai.prompts import (
    CONTENT_ANALYSIS_SYSTEM_PROMPT,
    SEARCH_QUERY_PARSE_SYSTEM_PROMPT,
    build_content_analysis_user_prompt,
)

logger = get_logger(__name__)

_RETRYABLE = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
)


def _proxied_http_client(proxy_url: str | None) -> httpx.AsyncClient | None:
    """Routes the OpenAI SDK's outbound calls through PROXY_URL when set --
    needed on VPS networks that can't reach api.openai.com directly.
    """
    return httpx.AsyncClient(proxy=proxy_url) if proxy_url else None


class OpenAIProvider:
    """Implements LLMProvider and VisionProvider."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.ai_api_key or None,
            base_url=settings.ai_base_url or None,
            timeout=settings.ai_request_timeout_seconds,
            http_client=_proxied_http_client(settings.proxy_url),
        )
        self._model = settings.ai_model
        self._vision_model = settings.vision_model

    @_RETRYABLE
    async def analyze_content(self, metadata: ContentMetadata) -> ContentAnalysis:
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": CONTENT_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": build_content_analysis_user_prompt(metadata)},
                ],
                response_format=ContentAnalysis,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_analyze_content_failed", error=str(exc))
            raise AIProviderError(str(exc)) from exc

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise AIProviderError("OpenAI returned no parsed content analysis")
        return parsed

    @_RETRYABLE
    async def parse_search_query(self, query: str) -> SearchFilter | None:
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": SEARCH_QUERY_PARSE_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                response_format=SearchFilter,
            )
            return completion.choices[0].message.parsed
        except Exception as exc:  # noqa: BLE001
            logger.info("openai_parse_search_query_failed", error=str(exc))
            return None

    @_RETRYABLE
    async def analyze_image(
        self, image_bytes: bytes, mime_type: str, caption: str | None = None
    ) -> ContentAnalysis:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        user_text = (
            "This is a screenshot or photo the user saved. Analyze what it shows "
            "(restaurant, product, recipe, quote, place, outfit, etc.) and classify it."
        )
        if caption:
            user_text += f"\nUser's Telegram caption: {caption}"

        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self._vision_model,
                messages=[
                    {"role": "system", "content": CONTENT_ANALYSIS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                response_format=ContentAnalysis,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_analyze_image_failed", error=str(exc))
            raise AIProviderError(str(exc)) from exc

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise AIProviderError("OpenAI returned no parsed image analysis")
        return parsed


class OpenAIEmbeddingProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.ai_api_key or None,
            base_url=settings.ai_base_url or None,
            timeout=settings.ai_request_timeout_seconds,
            http_client=_proxied_http_client(settings.proxy_url),
        )
        self._model = settings.embedding_model
        self._dimensions = settings.embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @_RETRYABLE
    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.embeddings.create(
                model=self._model, input=text[:8000]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("openai_embed_failed", error=str(exc))
            raise AIProviderError(str(exc)) from exc
        return response.data[0].embedding
