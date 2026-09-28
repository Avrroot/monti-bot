"""Hybrid natural-language search over a user's saved library.

query -> (optional) LLM filter parse -> embedding -> hybrid_search (lexical +
semantic + metadata + recency, see SavedItemRepository.hybrid_search).
If the LLM parser is unavailable or fails, search still works via the raw
query text for both lexical and semantic scoring.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.repositories.saved_items import SavedItemRepository, ScoredItem
from app.schemas.content import SearchFilter
from app.services.ai.base import AIProviderError
from app.services.ai.factory import get_embedding_provider, get_llm_provider

logger = get_logger(__name__)


async def search_library(
    session: AsyncSession, *, user_id: uuid.UUID, query_text: str
) -> list[ScoredItem]:
    settings = get_settings()
    items_repo = SavedItemRepository(session)

    filters = await _try_parse_filters(query_text)
    semantic_query = (filters.semantic_query if filters and filters.semantic_query else query_text)

    embedding = await _try_embed(semantic_query)

    return await items_repo.hybrid_search(
        user_id,
        lexical_query=query_text,
        query_embedding=embedding,
        filters=filters,
        weights=settings.search_weights,
        limit=settings.search_result_limit,
        min_score=settings.search_min_score,
    )


async def _try_parse_filters(query_text: str) -> SearchFilter | None:
    try:
        llm = get_llm_provider()
        return await llm.parse_search_query(query_text)
    except AIProviderError as exc:
        logger.info("search_filter_parse_degraded", error=str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("search_filter_parse_failed", error=str(exc))
        return None


async def _try_embed(text: str) -> list[float] | None:
    try:
        embedder = get_embedding_provider()
        return await embedder.embed(text)
    except AIProviderError as exc:
        logger.info("search_embed_degraded", error=str(exc))
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("search_embed_failed", error=str(exc))
        return None
