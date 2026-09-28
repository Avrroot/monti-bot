"""Prompt templates for AI classification / search-query parsing.

Kept in one place so tone and the controlled category vocabulary stay
consistent across providers.
"""

from __future__ import annotations

from app.db.models.enums import Category
from app.schemas.content import ContentMetadata

_CATEGORY_LIST = ", ".join(c.value for c in Category)

CONTENT_ANALYSIS_SYSTEM_PROMPT = f"""You are the content-understanding engine of SaveBot, a personal \
knowledge-capture app. Given metadata extracted from a link (title, description, author, page \
text, transcript), produce a structured analysis that lets the user find this item later by \
describing it in their own words, in Russian or English.

Rules:
- `category` MUST be exactly one of: {_CATEGORY_LIST}. Never invent a new category.
- `subcategory` may be a short free-form string (e.g. "паста", "спальня", "силовая тренировка") \
or null if nothing specific applies.
- `title` should be short and human-friendly (rewrite a bad/clickbait title if needed).
- `summary` is 1-3 sentences describing what the content actually is/offers.
- `tags` are 3-8 short lowercase keywords a user might search by.
- `entities` are named things mentioned: places, brands, dishes, people, books, movies, products.
- `searchable_text` concatenates every fact a future natural-language search should be able to \
match against (title, summary, key entities, location, tags) in plain text.
- `language` is the ISO 639-1 code of the content's primary language.
- `location` is filled only if the content clearly refers to a real place (city/venue).
- If information is missing or extraction was partial, make a reasonable best-effort guess from \
what's available rather than leaving fields empty, but do not fabricate specific facts (prices, \
addresses) that aren't present in the source.
"""

SEARCH_QUERY_PARSE_SYSTEM_PROMPT = f"""You turn a user's natural-language search over their own \
saved-content library into structured filters. The user writes in Russian or English.

Rules:
- `query` is the original user text, unchanged.
- `semantic_query` is a cleaned-up version of the query suited for embedding similarity search \
(strip filler words like "найди", "покажи", "где было").
- `category`, if a category is clearly implied, MUST be exactly one of: {_CATEGORY_LIST}. \
Otherwise null.
- `platform` if the user names a specific platform (instagram, tiktok, youtube, youtube_shorts, \
pinterest, threads, web). Otherwise null.
- `location`, `tags`, `date_from`, `date_to` (ISO 8601 dates), `favorites_only` only if clearly \
implied. Do not guess aggressively — when unsure, leave the field null/empty so plain hybrid \
search over the full query can still work.
"""


def build_content_analysis_user_prompt(metadata: ContentMetadata) -> str:
    parts = [
        f"Platform: {metadata.platform.value}",
        f"URL: {metadata.url}",
    ]
    if metadata.title:
        parts.append(f"Title: {metadata.title}")
    if metadata.description:
        parts.append(f"Description: {metadata.description}")
    if metadata.author:
        parts.append(f"Author: {metadata.author}")
    if metadata.transcript:
        parts.append(f"Transcript: {metadata.transcript[:4000]}")
    if metadata.extracted_text:
        parts.append(f"Page text: {metadata.extracted_text[:4000]}")
    if not metadata.extraction_succeeded:
        parts.append(
            "Note: extraction was only partially successful; work with what's available above."
        )
    return "\n".join(parts)
