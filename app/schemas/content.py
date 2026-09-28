"""Pydantic schemas shared across extractors, AI services, and repositories."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import Category, ExtractionMethod, MediaType, Platform


class ContentMetadata(BaseModel):
    """Unified output of any ContentExtractor implementation."""

    model_config = ConfigDict(extra="forbid")

    url: str
    canonical_url: str
    platform: Platform
    title: str | None = None
    description: str | None = None
    author: str | None = None
    thumbnail_url: str | None = None
    media_type: MediaType = MediaType.UNKNOWN
    transcript: str | None = None
    extracted_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    extraction_method: ExtractionMethod = ExtractionMethod.NONE
    extraction_succeeded: bool = True
    extraction_warning: str | None = None


class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str = Field(description="e.g. person, place, brand, dish, book, movie")


class LocationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    city: str | None = None
    country: str | None = None


class ContentAnalysis(BaseModel):
    """Strict structured output produced by the LLM classification step."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    content_type: str
    category: Category
    subcategory: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=15)
    entities: list[EntityRef] = Field(default_factory=list)
    searchable_text: str
    language: str = "ru"
    location: LocationInfo | None = None
    structured_data: dict[str, Any] = Field(default_factory=dict)


class SearchFilter(BaseModel):
    """Structured filters optionally extracted from a natural-language query."""

    model_config = ConfigDict(extra="forbid")

    query: str
    semantic_query: str | None = None
    category: Category | None = None
    subcategory: str | None = None
    platform: Platform | None = None
    tags: list[str] = Field(default_factory=list)
    location: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    favorites_only: bool = False
    collection_id: str | None = None
