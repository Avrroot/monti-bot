"""Anthropic-backed LLMProvider/VisionProvider implementation.

Demonstrates the abstraction is not tied to one vendor. Structured output is
achieved via a forced tool call (Claude has no embeddings endpoint, so
`AnthropicProvider` does NOT implement EmbeddingProvider — pair it with
`OpenAIEmbeddingProvider` or another embedding provider via the
EMBEDDING_PROVIDER env var).
"""

from __future__ import annotations

import base64

import httpx
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage
from pydantic import BaseModel, ValidationError
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

_ANALYSIS_TOOL_NAME = "emit_content_analysis"
_SEARCH_FILTER_TOOL_NAME = "emit_search_filter"


def _tool_for(model_cls: type[BaseModel], name: str) -> dict:
    schema = model_cls.model_json_schema()
    return {"name": name, "description": f"Emit a {model_cls.__name__}", "input_schema": schema}


def _extract_tool_input(message: AnthropicMessage, tool_name: str) -> dict | None:
    for block in message.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    return None


class AnthropicProvider:
    """Implements LLMProvider and VisionProvider (no embeddings)."""

    def __init__(self) -> None:
        settings = get_settings()
        http_client = httpx.AsyncClient(proxy=settings.proxy_url) if settings.proxy_url else None
        self._client = AsyncAnthropic(
            api_key=settings.ai_api_key or None,
            timeout=settings.ai_request_timeout_seconds,
            http_client=http_client,
        )
        self._model = settings.ai_model
        self._vision_model = settings.vision_model

    @_RETRYABLE
    async def analyze_content(self, metadata: ContentMetadata) -> ContentAnalysis:
        tool = _tool_for(ContentAnalysis, _ANALYSIS_TOOL_NAME)
        try:
            message = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=2000,
                system=CONTENT_ANALYSIS_SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": _ANALYSIS_TOOL_NAME},
                messages=[
                    {"role": "user", "content": build_content_analysis_user_prompt(metadata)}
                ],
            )
            data = _extract_tool_input(message, _ANALYSIS_TOOL_NAME)
            if data is None:
                raise AIProviderError("Anthropic response had no tool_use block")
            return ContentAnalysis.model_validate(data)
        except (AIProviderError, ValidationError):
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("anthropic_analyze_content_failed", error=str(exc))
            raise AIProviderError(str(exc)) from exc

    @_RETRYABLE
    async def parse_search_query(self, query: str) -> SearchFilter | None:
        tool = _tool_for(SearchFilter, _SEARCH_FILTER_TOOL_NAME)
        try:
            message = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=500,
                system=SEARCH_QUERY_PARSE_SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": _SEARCH_FILTER_TOOL_NAME},
                messages=[{"role": "user", "content": query}],
            )
            data = _extract_tool_input(message, _SEARCH_FILTER_TOOL_NAME)
            return SearchFilter.model_validate(data) if data else None
        except Exception as exc:  # noqa: BLE001
            logger.info("anthropic_parse_search_query_failed", error=str(exc))
            return None

    @_RETRYABLE
    async def analyze_image(
        self, image_bytes: bytes, mime_type: str, caption: str | None = None
    ) -> ContentAnalysis:
        tool = _tool_for(ContentAnalysis, _ANALYSIS_TOOL_NAME)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        user_text = (
            "This is a screenshot or photo the user saved. Analyze what it shows "
            "and classify it."
        )
        if caption:
            user_text += f"\nUser's Telegram caption: {caption}"

        try:
            message = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._vision_model,
                max_tokens=2000,
                system=CONTENT_ANALYSIS_SYSTEM_PROMPT,
                tools=[tool],
                tool_choice={"type": "tool", "name": _ANALYSIS_TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": b64,
                                },
                            },
                        ],
                    }
                ],
            )
            data = _extract_tool_input(message, _ANALYSIS_TOOL_NAME)
            if data is None:
                raise AIProviderError("Anthropic response had no tool_use block")
            return ContentAnalysis.model_validate(data)
        except (AIProviderError, ValidationError):
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("anthropic_analyze_image_failed", error=str(exc))
            raise AIProviderError(str(exc)) from exc
