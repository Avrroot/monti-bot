from __future__ import annotations

from app.db.models.enums import Category
from app.schemas.content import ContentAnalysis, EntityRef, LocationInfo
from app.services.content.searchable_text import (
    build_searchable_text,
    searchable_text_from_analysis,
)


def test_build_searchable_text_includes_user_note() -> None:
    text = build_searchable_text(
        title="Girafe Paris",
        summary="Ресторан с видом на Eiffel Tower",
        description=None,
        author=None,
        platform="instagram",
        category="restaurants",
        subcategory=None,
        tags=["ресторан", "париж"],
        entities=["Eiffel Tower"],
        location="Paris",
        user_note="Сходить сюда с Машей",
    )
    assert "Сходить сюда с Машей" in text
    assert "Eiffel Tower" in text
    assert "париж" in text


def test_build_searchable_text_skips_none_fields() -> None:
    text = build_searchable_text(
        title="Test",
        summary=None,
        description=None,
        author=None,
        platform="web",
        category=None,
        subcategory=None,
        tags=[],
        entities=[],
        location=None,
        user_note=None,
    )
    assert text.strip() == "Test \nweb"


def test_searchable_text_from_analysis_includes_location() -> None:
    analysis = ContentAnalysis(
        title="Girafe Paris",
        summary="Ресторан с видом на башню",
        content_type="restaurant",
        category=Category.RESTAURANTS,
        tags=["ресторан"],
        entities=[EntityRef(name="Eiffel Tower", type="place")],
        searchable_text="girafe paris rooftop restaurant",
        location=LocationInfo(name="Girafe", city="Paris", country="France"),
    )
    text = searchable_text_from_analysis(analysis, platform="instagram", user_note="с Машей")
    assert "Paris" in text
    assert "с Машей" in text
    assert "Eiffel Tower" in text
