"""YouTube / YouTube Shorts extractor.

Uses the public noembed-free YouTube oEmbed endpoint (no API key required):
https://www.youtube.com/oembed?url=...&format=json

This yields title/author/thumbnail reliably. Full descriptions and caption
transcripts require the YouTube Data API v3 (needs an API key) or
authenticated scraping, which is out of scope for the MVP — captured as a
documented limitation. If YOUTUBE_API_KEY is ever added to config, this is
the extension point for richer metadata.
"""

from __future__ import annotations

from urllib.parse import quote

from app.db.models.enums import ExtractionMethod, MediaType, Platform
from app.extractors.base import ContentExtractor
from app.extractors.oembed import fetch_oembed
from app.extractors.web import WebExtractor
from app.schemas.content import ContentMetadata

_OEMBED_URL = "https://www.youtube.com/oembed?url={url}&format=json"


class YouTubeExtractor(ContentExtractor):
    platform = Platform.YOUTUBE

    def __init__(self) -> None:
        self._web_fallback = WebExtractor()

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        is_short = "/shorts/" in url
        platform = Platform.YOUTUBE_SHORTS if is_short else Platform.YOUTUBE

        data = await fetch_oembed(_OEMBED_URL.format(url=quote(url, safe="")))

        if not data:
            fallback = await self._web_fallback.extract(url, canonical_url)
            return fallback.model_copy(update={"platform": platform})

        return ContentMetadata(
            url=url,
            canonical_url=canonical_url,
            platform=platform,
            title=data.get("title"),
            author=data.get("author_name"),
            thumbnail_url=data.get("thumbnail_url"),
            media_type=MediaType.VIDEO,
            metadata={
                "provider_name": data.get("provider_name"),
                "author_url": data.get("author_url"),
            },
            extraction_method=ExtractionMethod.OEMBED,
            extraction_succeeded=True,
        )
