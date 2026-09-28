"""TikTok extractor via the public oEmbed endpoint (no auth required):
https://www.tiktok.com/oembed?url=...
Falls back to generic OpenGraph extraction if oEmbed is unavailable
(private/removed videos, endpoint changes, etc).
"""

from __future__ import annotations

from urllib.parse import quote

from app.db.models.enums import ExtractionMethod, MediaType, Platform
from app.extractors.base import ContentExtractor
from app.extractors.oembed import fetch_oembed
from app.extractors.web import WebExtractor
from app.schemas.content import ContentMetadata

_OEMBED_URL = "https://www.tiktok.com/oembed?url={url}"


class TikTokExtractor(ContentExtractor):
    platform = Platform.TIKTOK

    def __init__(self) -> None:
        self._web_fallback = WebExtractor()

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        data = await fetch_oembed(_OEMBED_URL.format(url=quote(url, safe="")))

        if not data:
            fallback = await self._web_fallback.extract(url, canonical_url)
            return fallback.model_copy(update={"platform": Platform.TIKTOK})

        return ContentMetadata(
            url=url,
            canonical_url=canonical_url,
            platform=Platform.TIKTOK,
            title=data.get("title"),
            author=data.get("author_name"),
            thumbnail_url=data.get("thumbnail_url"),
            media_type=MediaType.VIDEO,
            metadata={"author_url": data.get("author_url")},
            extraction_method=ExtractionMethod.OEMBED,
            extraction_succeeded=True,
        )
