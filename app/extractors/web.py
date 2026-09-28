"""Generic web page extractor: OpenGraph -> JSON-LD -> HTML meta -> visible text.

Used directly for arbitrary URLs, and as the fallback path for platform
extractors (Threads, and Instagram/TikTok/Pinterest when oEmbed fails).
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.db.models.enums import ExtractionMethod, MediaType, Platform
from app.extractors.base import ContentExtractor
from app.schemas.content import ContentMetadata
from app.services.security.safe_http import (
    ResponseTooLargeError,
    UnsafeURLError,
    safe_get,
)

logger = get_logger(__name__)

_MAX_EXTRACTED_TEXT_CHARS = 6000


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_json_ld(soup: BeautifulSoup) -> dict:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)), {})
        if isinstance(data, dict) and data:
            return data
    return {}


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": f"og:{prop}"}) or soup.find(
        "meta", attrs={"name": f"og:{prop}"}
    )
    if tag and tag.get("content"):
        return _clean_text(str(tag["content"]))
    return None


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return _clean_text(str(tag["content"]))
    return None


def _visible_text(soup: BeautifulSoup, limit: int) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "head"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return _clean_text(text)[:limit]


class WebExtractor(ContentExtractor):
    platform = Platform.WEB

    async def extract(self, url: str, canonical_url: str) -> ContentMetadata:
        try:
            response = await safe_get(
                url,
                accept_content_types=("text/html", "application/xhtml+xml"),
            )
        except (UnsafeURLError, ResponseTooLargeError) as exc:
            logger.warning("web_extract_blocked", url=canonical_url, error=str(exc))
            return self._fallback(url, canonical_url, "Не удалось безопасно загрузить страницу")
        except Exception as exc:  # noqa: BLE001 - never let extraction crash the pipeline
            logger.warning("web_extract_failed", url=canonical_url, error=str(exc))
            return self._fallback(url, canonical_url, "Не удалось загрузить страницу")

        if response.status_code >= 400:
            return self._fallback(
                url, canonical_url, f"Страница вернула ошибку {response.status_code}"
            )

        try:
            soup = BeautifulSoup(response.content, "lxml")
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_parse_failed", url=canonical_url, error=str(exc))
            return self._fallback(url, canonical_url, "Не удалось разобрать страницу")

        json_ld = _extract_json_ld(soup)

        title = (
            _og(soup, "title")
            or json_ld.get("headline")
            or json_ld.get("name")
            or (soup.title.string.strip() if soup.title and soup.title.string else None)
        )
        description = (
            _og(soup, "description")
            or json_ld.get("description")
            or _meta(soup, "description")
        )
        author = None
        json_author = json_ld.get("author")
        if isinstance(json_author, dict):
            author = json_author.get("name")
        elif isinstance(json_author, str):
            author = json_author

        thumbnail_url = _og(soup, "image")
        if not thumbnail_url:
            image_field = json_ld.get("image")
            if isinstance(image_field, str):
                thumbnail_url = image_field
            elif isinstance(image_field, list) and image_field:
                thumbnail_url = image_field[0]
            elif isinstance(image_field, dict):
                thumbnail_url = image_field.get("url")

        og_type = _og(soup, "type") or ""
        media_type = MediaType.VIDEO if "video" in og_type else MediaType.ARTICLE

        extracted_text = _visible_text(soup, _MAX_EXTRACTED_TEXT_CHARS)

        method = (
            ExtractionMethod.JSON_LD
            if json_ld
            else (ExtractionMethod.OPENGRAPH if _og(soup, "title") else ExtractionMethod.HTML_META)
        )

        return ContentMetadata(
            url=url,
            canonical_url=canonical_url,
            platform=Platform.WEB,
            title=title,
            description=description,
            author=author,
            thumbnail_url=thumbnail_url,
            media_type=media_type,
            extracted_text=extracted_text or None,
            metadata={"json_ld_type": json_ld.get("@type")} if json_ld else {},
            extraction_method=method,
            extraction_succeeded=bool(title or description or extracted_text),
        )
