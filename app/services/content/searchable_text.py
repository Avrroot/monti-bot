"""Builds the flat `searchable_text` blob that feeds full-text search.

Kept as a pure function so both the initial-save pipeline and the
edit/note-update paths can rebuild it deterministically without duplicating
the field list.
"""

from __future__ import annotations

from app.db.models.saved_item import SavedItem
from app.schemas.content import ContentAnalysis


def build_searchable_text(
    *,
    title: str | None,
    summary: str | None,
    description: str | None,
    author: str | None,
    platform: str | None,
    category: str | None,
    subcategory: str | None,
    tags: list[str],
    entities: list[str],
    location: str | None,
    user_note: str | None,
    transcript: str | None = None,
) -> str:
    parts = [
        title,
        summary,
        description,
        author,
        platform,
        category,
        subcategory,
        " ".join(tags),
        " ".join(entities),
        location,
        user_note,
        (transcript or "")[:2000] or None,
    ]
    return " \n".join(p for p in parts if p)


def searchable_text_from_analysis(
    analysis: ContentAnalysis, platform: str, user_note: str | None = None
) -> str:
    return build_searchable_text(
        title=analysis.title,
        summary=analysis.summary,
        description=None,
        author=None,
        platform=platform,
        category=analysis.category.value,
        subcategory=analysis.subcategory,
        tags=analysis.tags,
        entities=[e.name for e in analysis.entities],
        location=analysis.location.name if analysis.location else None,
        user_note=user_note,
        transcript=analysis.searchable_text,
    )


def rebuild_searchable_text_for_item(item: SavedItem, tags: list[str]) -> str:
    location = None
    if isinstance(item.structured_data, dict):
        loc = item.structured_data.get("location")
        if isinstance(loc, dict):
            location = loc.get("name") or loc.get("city")

    return build_searchable_text(
        title=item.title,
        summary=item.summary,
        description=item.description,
        author=item.author,
        platform=item.platform,
        category=item.category,
        subcategory=item.subcategory,
        tags=tags,
        entities=[],
        location=location,
        user_note=item.user_note,
        transcript=item.transcript,
    )
