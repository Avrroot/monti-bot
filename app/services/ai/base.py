"""AI provider abstraction layer.

Business logic (content analysis pipeline, search) depends only on these
Protocols, never on a specific vendor SDK. Concrete implementations live in
`openai_provider.py` / `anthropic_provider.py` and are selected at runtime by
`factory.py` based on the AI_PROVIDER / EMBEDDING_PROVIDER / VISION_PROVIDER
env vars.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.content import ContentAnalysis, ContentMetadata, SearchFilter


class LLMProvider(Protocol):
    async def analyze_content(self, metadata: ContentMetadata) -> ContentAnalysis:
        """Classify extracted content metadata into a structured ContentAnalysis."""
        ...

    async def parse_search_query(self, query: str) -> SearchFilter | None:
        """Best-effort structured parse of a natural-language search query.
        Returns None if parsing is unavailable/fails — callers must fall back
        to plain hybrid search in that case.
        """
        ...


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]:
        """Return a dense embedding vector for `text`."""
        ...

    @property
    def dimensions(self) -> int: ...


class VisionProvider(Protocol):
    async def analyze_image(
        self, image_bytes: bytes, mime_type: str, caption: str | None = None
    ) -> ContentAnalysis:
        """Understand an image (screenshot/photo) and return a structured
        ContentAnalysis, same shape as text-based analysis.
        """
        ...


class AIProviderError(Exception):
    """Raised when an AI call fails after retries; callers must degrade
    gracefully (save the item with minimal metadata) rather than crash.
    """
