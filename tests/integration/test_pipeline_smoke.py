"""End-to-end smoke test of the save pipeline against a real DB, with the AI
provider and extractor faked out (no live network/AI calls -- see repo
testing philosophy in README). Exercises the exact code path the worker runs:
extract -> analyze -> tag -> embed -> persist -> COMPLETED.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.db.models.enums import Category, ExtractionMethod, MediaType, Platform, ProcessingStatus
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.db.repositories.users import UserRepository
from app.schemas.content import ContentAnalysis, ContentMetadata
from app.services.content.pipeline import process_url_save

pytestmark = pytest.mark.integration


async def test_process_url_save_end_to_end(db_session):
    users = UserRepository(db_session)
    items = SavedItemRepository(db_session)
    tags_repo = TagRepository(db_session)

    user = await users.get_or_create(
        telegram_user_id=42001, username="smoke", first_name="Smoke", locale="ru"
    )
    item = await items.create(
        user_id=user.id,
        url="https://example.com/recipes/carbonara",
        canonical_url="https://example.com/recipes/carbonara",
        platform=Platform.WEB.value,
        processing_status=ProcessingStatus.PENDING,
    )
    await db_session.flush()

    fake_metadata = ContentMetadata(
        url="https://example.com/recipes/carbonara",
        canonical_url="https://example.com/recipes/carbonara",
        platform=Platform.WEB,
        title="Классическая карбонара",
        description="Рецепт пасты карбонара за 15 минут",
        thumbnail_url="https://example.com/img.jpg",
        media_type=MediaType.ARTICLE,
        extracted_text="Паста карбонара: яйца, гуанчиале, пекорино, перец.",
        extraction_method=ExtractionMethod.OPENGRAPH,
        extraction_succeeded=True,
    )
    fake_analysis = ContentAnalysis(
        title="Паста карбонара за 15 минут",
        summary="Быстрый рецепт классической карбонары.",
        content_type="recipe",
        category=Category.RECIPES,
        subcategory="паста",
        tags=["карбонара", "паста", "ужин", "быстро"],
        searchable_text="паста карбонара рецепт ужин быстро",
        language="ru",
    )

    with (
        patch("app.services.content.pipeline.get_extractor") as mock_get_extractor,
        patch("app.services.content.pipeline.get_llm_provider") as mock_get_llm,
        patch("app.services.content.pipeline.get_embedding_provider") as mock_get_embedder,
    ):
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = fake_metadata
        mock_get_extractor.return_value = mock_extractor

        mock_llm = AsyncMock()
        mock_llm.analyze_content.return_value = fake_analysis
        mock_get_llm.return_value = mock_llm

        mock_embedder = AsyncMock()
        mock_embedder.embed.return_value = [0.01] * 1536
        mock_get_embedder.return_value = mock_embedder

        result = await process_url_save(
            db_session,
            user_id=user.id,
            saved_item_id=item.id,
            raw_url="https://example.com/recipes/carbonara",
        )

    assert result is not None
    assert result.processing_status == ProcessingStatus.COMPLETED
    assert result.title == "Паста карбонара за 15 минут"
    assert result.category == Category.RECIPES.value
    assert result.subcategory == "паста"
    assert result.embedding is not None

    tags = await tags_repo.list_for_item(item.id)
    assert set(tags) == {"карбонара", "паста", "ужин", "быстро"}

    # the item must now be findable via hybrid search using only the raw query text
    from app.core.config import SearchWeights

    results = await items.hybrid_search(
        user.id,
        lexical_query="карбонара",
        query_embedding=None,
        filters=None,
        weights=SearchWeights(),
        limit=10,
        min_score=0.0,
    )
    assert any(r.item.id == item.id for r in results)


async def test_process_url_save_degrades_gracefully_on_ai_failure(db_session):
    from app.services.ai.base import AIProviderError

    users = UserRepository(db_session)
    items = SavedItemRepository(db_session)

    user = await users.get_or_create(
        telegram_user_id=42002, username="smoke2", first_name="Smoke", locale="ru"
    )
    item = await items.create(
        user_id=user.id,
        url="https://example.com/x",
        canonical_url="https://example.com/x",
        platform=Platform.WEB.value,
        processing_status=ProcessingStatus.PENDING,
    )
    await db_session.flush()

    fake_metadata = ContentMetadata(
        url="https://example.com/x",
        canonical_url="https://example.com/x",
        platform=Platform.WEB,
        title="Some Page",
        extraction_succeeded=True,
    )

    with (
        patch("app.services.content.pipeline.get_extractor") as mock_get_extractor,
        patch("app.services.content.pipeline.get_llm_provider") as mock_get_llm,
        patch("app.services.content.pipeline.get_embedding_provider") as mock_get_embedder,
    ):
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = fake_metadata
        mock_get_extractor.return_value = mock_extractor

        mock_llm = AsyncMock()
        mock_llm.analyze_content.side_effect = AIProviderError("AI is down")
        mock_get_llm.return_value = mock_llm

        mock_embedder = AsyncMock()
        mock_embedder.embed.side_effect = AIProviderError("embeddings down")
        mock_get_embedder.return_value = mock_embedder

        result = await process_url_save(
            db_session,
            user_id=user.id,
            saved_item_id=item.id,
            raw_url="https://example.com/x",
        )

    # the save must still complete -- AI failure degrades gracefully, never loses the item
    assert result is not None
    assert result.processing_status == ProcessingStatus.COMPLETED
    assert result.title  # fallback title populated
    assert result.embedding is None
