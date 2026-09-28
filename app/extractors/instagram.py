"""Instagram extractor.

Meta deprecated the public (keyless) Instagram oEmbed endpoint in 2020 — it
now requires a Facebook Graph API app token tied to an approved app. Without
that credential (none is requested in this MVP's env, see .env.example) we
fall back to OpenGraph/JSON-LD scraping of the public page, which Instagram
serves in reduced form to logged-out requests. This is a documented
limitation: expect title/thumbnail more often than full captions, and expect
some posts (private accounts, age-gated content) to yield nothing beyond the
URL itself — the pipeline still saves the link in that case.
"""

from __future__ import annotations

from app.db.models.enums import MediaType, Platform
from app.extractors.base import ContentExtractor
from app.extractors.web import WebExtractor
from app.schemas.content import ContentMetadata


class InstagramExtractor(ContentExtractor):
    platform = Platform.INSTAGRAM

    def __init__(self) -> None:
        self._web_fallback = WebExtractor()

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        result = await self._web_fallback.extract(url, canonical_url)
        media_type = MediaType.VIDEO if "/reel/" in url else result.media_type
        return result.model_copy(update={"platform": Platform.INSTAGRAM, "media_type": media_type})
