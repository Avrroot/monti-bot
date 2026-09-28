"""ContentExtractor interface.

Every extractor takes a normalized URL and returns a ContentMetadata object.
Extractors must never raise on "couldn't get everything" — partial metadata
with `extraction_succeeded=False` / `extraction_warning` set is always
preferable to losing the save entirely (product principle: never lose the
user's link).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.models.enums import Platform
from app.schemas.content import ContentMetadata


class ContentExtractor(ABC):
    platform: Platform

    @abstractmethod
    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        """Fetch and normalize metadata for `url`. Must not raise for
        ordinary extraction failures (network errors, missing oEmbed, private
        content) — degrade gracefully and set extraction_succeeded=False.
        """
        raise NotImplementedError

    def _fallback(
        self, url: str, canonical_url: str, warning: str
    ) -> ContentMetadata:
        return ContentMetadata(
            url=url,
            canonical_url=canonical_url,
            platform=self.platform,
            extraction_succeeded=False,
            extraction_warning=warning,
        )
