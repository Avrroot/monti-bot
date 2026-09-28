"""Threads extractor.

Threads has no public oEmbed endpoint, so this relies entirely on
OpenGraph/JSON-LD metadata from the public post page via WebExtractor.
"""

from __future__ import annotations

from app.db.models.enums import Platform
from app.extractors.base import ContentExtractor
from app.extractors.web import WebExtractor
from app.schemas.content import ContentMetadata


class ThreadsExtractor(ContentExtractor):
    platform = Platform.THREADS

    def __init__(self) -> None:
        self._web_fallback = WebExtractor()

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        result = await self._web_fallback.extract(url, canonical_url)
        return result.model_copy(update={"platform": Platform.THREADS})
