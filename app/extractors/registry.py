from __future__ import annotations

from app.db.models.enums import Platform
from app.extractors.base import ContentExtractor
from app.extractors.instagram import InstagramExtractor
from app.extractors.pinterest import PinterestExtractor
from app.extractors.threads import ThreadsExtractor
from app.extractors.tiktok import TikTokExtractor
from app.extractors.web import WebExtractor
from app.extractors.youtube import YouTubeExtractor

_WEB = WebExtractor()

_REGISTRY: dict[Platform, ContentExtractor] = {
    Platform.INSTAGRAM: InstagramExtractor(),
    Platform.TIKTOK: TikTokExtractor(),
    Platform.YOUTUBE: YouTubeExtractor(),
    Platform.YOUTUBE_SHORTS: YouTubeExtractor(),
    Platform.PINTEREST: PinterestExtractor(),
    Platform.THREADS: ThreadsExtractor(),
    Platform.WEB: _WEB,
}


def get_extractor(platform: Platform) -> ContentExtractor:
    return _REGISTRY.get(platform, _WEB)
