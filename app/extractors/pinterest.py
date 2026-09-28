"""Pinterest extractor.

Tries Pinterest's oEmbed endpoint (https://www.pinterest.com/oembed.json)
first, then falls back to OpenGraph/JSON-LD via WebExtractor, since Pinterest
pin pages carry rich OG data (og:title, og:description, og:image) even when
oEmbed is unavailable for a given pin.
"""

from __future__ import annotations

from urllib.parse import quote

from app.db.models.enums import ExtractionMethod, MediaType, Platform
from app.extractors.base import ContentExtractor
from app.extractors.oembed import fetch_oembed
from app.extractors.web import WebExtractor
from app.schemas.content import ContentMetadata

_OEMBED_URL = "https://www.pinterest.com/oembed.json?url={url}"


class PinterestExtractor(ContentExtractor):
    platform = Platform.PINTEREST

    def __init__(self) -> None:
        self._web_fallback = WebExtractor()

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        data = await fetch_oembed(_OEMBED_URL.format(url=quote(url, safe="")))

        if data and data.get("title"):
            return ContentMetadata(
                url=url,
                canonical_url=canonical_url,
                platform=Platform.PINTEREST,
                title=data.get("title"),
                author=data.get("author_name"),
                thumbnail_url=data.get("thumbnail_url"),
                media_type=MediaType.IMAGE,
                metadata={"author_url": data.get("author_url")},
                extraction_method=ExtractionMethod.OEMBED,
                extraction_succeeded=True,
            )

        fallback = await self._web_fallback.extract(url, canonical_url)
        return fallback.model_copy(
            update={"platform": Platform.PINTEREST, "media_type": MediaType.IMAGE}
        )
