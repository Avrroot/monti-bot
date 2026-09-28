"""Orchestrates CAPTURE -> UNDERSTAND -> ORGANIZE for a single saved item.

Runs inside the arq worker (see app/workers/tasks.py), not in the Telegram
handler, so slow extraction/AI calls never block the bot's event loop.
Every step degrades gracefully: extraction failure still saves the URL,
AI failure still saves the raw metadata, embedding failure still saves the
analyzed item (just without semantic search reach until retried).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.enums import Category, ProcessingStatus
from app.db.models.saved_item import SavedItem
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.extractors.registry import get_extractor
from app.schemas.content import ContentAnalysis, ContentMetadata
from app.services.ai.base import AIProviderError
from app.services.ai.factory import get_embedding_provider, get_llm_provider, get_vision_provider
from app.services.content.searchable_text import searchable_text_from_analysis
from app.services.content.url_utils import detect_platform, normalize_url

logger = get_logger(__name__)


def _fallback_analysis(metadata: ContentMetadata) -> ContentAnalysis:
    """Used when the LLM call fails entirely — the item is still saved with
    whatever raw metadata extraction produced, just uncategorized.
    """
    title = metadata.title or metadata.url
    summary = metadata.description or "Не удалось автоматически проанализировать содержимое."
    return ContentAnalysis(
        title=title,
        summary=summary,
        content_type="unknown",
        category=Category.OTHER,
        subcategory=None,
        tags=[],
        entities=[],
        searchable_text=" ".join(filter(None, [title, summary, metadata.author])),
        language="ru",
        location=None,
        structured_data={},
    )


async def process_url_save(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    saved_item_id: uuid.UUID,
    raw_url: str,
) -> SavedItem | None:
    items = SavedItemRepository(session)
    tags_repo = TagRepository(session)

    item = await items.get(user_id, saved_item_id)
    if item is None:
        logger.warning("process_url_save_item_missing", saved_item_id=str(saved_item_id))
        return None

    canonical_url = normalize_url(raw_url)
    platform = detect_platform(canonical_url)

    try:
        item.processing_status = ProcessingStatus.EXTRACTING
        await session.flush()

        extractor = get_extractor(platform)
        metadata = await extractor.extract(raw_url, canonical_url)

        item.processing_status = ProcessingStatus.ANALYZING
        await session.flush()

        analysis = await _analyze(metadata)

        item.title = analysis.title
        item.description = metadata.description
        item.summary = analysis.summary
        item.author = metadata.author
        item.thumbnail_url = metadata.thumbnail_url
        item.media_type = metadata.media_type.value
        item.transcript = metadata.transcript
        item.extracted_text = metadata.extracted_text
        item.extraction_method = metadata.extraction_method.value
        item.content_type = analysis.content_type
        item.category = analysis.category.value
        item.subcategory = analysis.subcategory
        item.language = analysis.language
        item.structured_data = _jsonable(analysis.structured_data)
        item.item_metadata = _jsonable(metadata.metadata)
        item.searchable_text = searchable_text_from_analysis(
            analysis, platform.value, user_note=item.user_note
        )
        if not metadata.extraction_succeeded:
            item.processing_error = metadata.extraction_warning

        await tags_repo.set_tags_for_item(user_id, item.id, analysis.tags)

        item.processing_status = ProcessingStatus.INDEXING
        await session.flush()

        await _embed(items, item, analysis.searchable_text)

        item.processing_status = ProcessingStatus.COMPLETED
        await session.flush()

    except Exception as exc:  # noqa: BLE001 - pipeline must never crash the worker
        logger.error(
            "process_url_save_failed", saved_item_id=str(saved_item_id), error=str(exc)
        )
        item.processing_status = ProcessingStatus.FAILED
        item.processing_error = "internal_error"
        # Still keep whatever was captured (title/url) so the user doesn't lose the save.
        if not item.title:
            item.title = raw_url
        await session.flush()

    return item


async def process_image_save(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    saved_item_id: uuid.UUID,
    image_bytes: bytes,
    mime_type: str,
    caption: str | None,
) -> SavedItem | None:
    items = SavedItemRepository(session)
    tags_repo = TagRepository(session)

    item = await items.get(user_id, saved_item_id)
    if item is None:
        logger.warning("process_image_save_item_missing", saved_item_id=str(saved_item_id))
        return None

    try:
        item.processing_status = ProcessingStatus.ANALYZING
        await session.flush()

        vision = get_vision_provider()
        try:
            analysis = await vision.analyze_image(image_bytes, mime_type, caption)
        except AIProviderError:
            analysis = ContentAnalysis(
                title=caption or "Сохранённое изображение",
                summary="Не удалось автоматически проанализировать изображение.",
                content_type="image",
                category=Category.OTHER,
                tags=[],
                entities=[],
                searchable_text=caption or "изображение",
                language="ru",
            )

        item.title = analysis.title
        item.summary = analysis.summary
        item.content_type = analysis.content_type
        item.category = analysis.category.value
        item.subcategory = analysis.subcategory
        item.language = analysis.language
        item.structured_data = _jsonable(analysis.structured_data)
        item.media_type = "image"
        item.searchable_text = searchable_text_from_analysis(
            analysis, "telegram_image", user_note=item.user_note
        )

        await tags_repo.set_tags_for_item(user_id, item.id, analysis.tags)

        item.processing_status = ProcessingStatus.INDEXING
        await session.flush()

        await _embed(items, item, analysis.searchable_text)

        item.processing_status = ProcessingStatus.COMPLETED
        await session.flush()

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "process_image_save_failed", saved_item_id=str(saved_item_id), error=str(exc)
        )
        item.processing_status = ProcessingStatus.FAILED
        item.processing_error = "internal_error"
        if not item.title:
            item.title = caption or "Сохранённое изображение"
        await session.flush()

    return item


async def _analyze(metadata: ContentMetadata) -> ContentAnalysis:
    llm = get_llm_provider()
    try:
        return await llm.analyze_content(metadata)
    except AIProviderError as exc:
        logger.warning("llm_analyze_content_degraded", error=str(exc))
        return _fallback_analysis(metadata)


async def _embed(items: SavedItemRepository, item: Any, text: str) -> None:
    try:
        embedder = get_embedding_provider()
        vector = await embedder.embed(text or item.title or "")
        item.embedding = vector
    except AIProviderError as exc:
        logger.warning("embedding_failed", saved_item_id=str(item.id), error=str(exc))


def _jsonable(data: dict) -> dict:
    """Pydantic sub-models (EntityRef/LocationInfo) may still be present in
    structured_data if a provider echoes them back; make sure it's plain JSON.
    """
    return json.loads(json.dumps(data, default=str))
