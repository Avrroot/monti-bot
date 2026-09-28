"""Selects concrete AI provider implementations based on config.

Business logic should only ever import `get_llm_provider` / `get_embedding_provider`
/ `get_vision_provider` from this module — never a concrete provider class directly.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.ai.base import EmbeddingProvider, LLMProvider, VisionProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.ai_provider == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if settings.ai_provider == "openai":
        from app.services.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")


@lru_cache
def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.vision_provider == "anthropic":
        from app.services.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if settings.vision_provider == "openai":
        from app.services.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()
    raise ValueError(f"Unsupported VISION_PROVIDER: {settings.vision_provider}")


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        from app.services.ai.openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider()
    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider} "
        "(Anthropic has no embeddings endpoint; use 'openai' or add a new provider)"
    )
