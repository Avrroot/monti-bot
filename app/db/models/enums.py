"""Shared enums used by DB models and Pydantic schemas.

Categories are a controlled vocabulary owned by the application (per product
spec section 4): the AI classifier may only pick from `Category`, but it is
free to propose any `subcategory` string. Platforms and processing statuses
are likewise controlled; content_type stays a free indexed string because the
AI needs room to name new content shapes (restaurant, recipe, product, ...)
without a migration.
"""

from __future__ import annotations

from enum import StrEnum


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    YOUTUBE_SHORTS = "youtube_shorts"
    PINTEREST = "pinterest"
    THREADS = "threads"
    WEB = "web"
    TELEGRAM_IMAGE = "telegram_image"
    OTHER = "other"


class MediaType(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    CAROUSEL = "carousel"
    ARTICLE = "article"
    UNKNOWN = "unknown"


class Category(StrEnum):
    RESTAURANTS = "restaurants"
    RECIPES = "recipes"
    PRODUCTS = "products"
    FASHION = "fashion"
    TRAVEL = "travel"
    FITNESS = "fitness"
    BOOKS = "books"
    MOVIES_TV = "movies_tv"
    MUSIC = "music"
    PSYCHOLOGY = "psychology"
    WORK_BUSINESS = "work_business"
    IDEAS = "ideas"
    EDUCATION = "education"
    TOOLS_SERVICES = "tools_services"
    OTHER = "other"


CATEGORY_EMOJI: dict[Category, str] = {
    Category.RESTAURANTS: "🍽",
    Category.RECIPES: "🍳",
    Category.PRODUCTS: "🛍",
    Category.FASHION: "👗",
    Category.TRAVEL: "✈️",
    Category.FITNESS: "🏋️",
    Category.BOOKS: "📚",
    Category.MOVIES_TV: "🎬",
    Category.MUSIC: "🎵",
    Category.PSYCHOLOGY: "🧠",
    Category.WORK_BUSINESS: "💼",
    Category.IDEAS: "💡",
    Category.EDUCATION: "📚",
    Category.TOOLS_SERVICES: "🔧",
    Category.OTHER: "📌",
}


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionMethod(StrEnum):
    OEMBED = "oembed"
    OPENGRAPH = "opengraph"
    JSON_LD = "json_ld"
    HTML_META = "html_meta"
    PAGE_TEXT = "page_text"
    VISION = "vision"
    NONE = "none"
