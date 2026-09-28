from __future__ import annotations

import pytest
from app.db.models.enums import Category, Platform
from app.schemas.content import ContentAnalysis, ContentMetadata, SearchFilter
from pydantic import ValidationError


def test_content_analysis_rejects_invalid_category() -> None:
    with pytest.raises(ValidationError):
        ContentAnalysis(
            title="Test",
            summary="Test summary",
            content_type="restaurant",
            category="not_a_real_category",  # type: ignore[arg-type]
            searchable_text="test",
        )


def test_content_analysis_accepts_controlled_category() -> None:
    analysis = ContentAnalysis(
        title="Паста карбонара",
        summary="Быстрый рецепт",
        content_type="recipe",
        category=Category.RECIPES,
        subcategory="паста",
        tags=["паста", "ужин"],
        searchable_text="паста карбонара",
    )
    assert analysis.category == Category.RECIPES
    assert analysis.language == "ru"  # default


def test_content_analysis_tags_are_capped() -> None:
    with pytest.raises(ValidationError):
        ContentAnalysis(
            title="Test",
            summary="Test",
            content_type="other",
            category=Category.OTHER,
            tags=[f"tag{i}" for i in range(20)],
            searchable_text="test",
        )


def test_content_metadata_requires_platform_enum() -> None:
    metadata = ContentMetadata(
        url="https://example.com",
        canonical_url="https://example.com",
        platform=Platform.WEB,
    )
    assert metadata.extraction_succeeded is True
    assert metadata.extraction_method.value == "none"


def test_search_filter_optional_fields_default_empty() -> None:
    search_filter = SearchFilter(query="найди ресторан на крыше")
    assert search_filter.category is None
    assert search_filter.tags == []
    assert search_filter.favorites_only is False


def test_search_filter_rejects_unknown_platform() -> None:
    with pytest.raises(ValidationError):
        SearchFilter(query="test", platform="myspace")  # type: ignore[arg-type]
