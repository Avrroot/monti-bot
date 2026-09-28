from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, Select, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SearchWeights
from app.db.models.collection import Collection, CollectionItem
from app.db.models.saved_item import SavedItem
from app.schemas.content import SearchFilter


def _try_parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass(slots=True)
class ScoredItem:
    item: SavedItem
    score: float
    semantic_score: float
    lexical_score: float
    metadata_score: float
    recency_score: float


class SavedItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _base_query(self, user_id: uuid.UUID) -> Select:
        return select(SavedItem).where(SavedItem.user_id == user_id)

    async def create(self, **fields: Any) -> SavedItem:
        item = SavedItem(**fields)
        self._session.add(item)
        await self._session.flush()
        return item

    async def get(self, user_id: uuid.UUID, item_id: uuid.UUID) -> SavedItem | None:
        stmt = self._base_query(user_id).where(SavedItem.id == item_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_by_canonical_url(
        self, user_id: uuid.UUID, canonical_url: str
    ) -> SavedItem | None:
        stmt = self._base_query(user_id).where(SavedItem.canonical_url == canonical_url)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_recent(
        self, user_id: uuid.UUID, limit: int = 10, offset: int = 0
    ) -> list[SavedItem]:
        stmt = (
            self._base_query(user_id)
            .order_by(SavedItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def list_favorites(
        self, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> list[SavedItem]:
        stmt = (
            self._base_query(user_id)
            .where(SavedItem.is_favorite.is_(True))
            .order_by(SavedItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count(SavedItem.id)).where(SavedItem.user_id == user_id)
        return (await self._session.execute(stmt)).scalar_one()

    async def counts_by_category(self, user_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(SavedItem.category, func.count(SavedItem.id))
            .where(SavedItem.user_id == user_id)
            .group_by(SavedItem.category)
        )
        rows = (await self._session.execute(stmt)).all()
        return {category: count for category, count in rows if category is not None}

    async def set_favorite(
        self, user_id: uuid.UUID, item_id: uuid.UUID, is_favorite: bool
    ) -> SavedItem | None:
        item = await self.get(user_id, item_id)
        if item is None:
            return None
        item.is_favorite = is_favorite
        await self._session.flush()
        return item

    async def update_fields(
        self, user_id: uuid.UUID, item_id: uuid.UUID, **fields: Any
    ) -> SavedItem | None:
        item = await self.get(user_id, item_id)
        if item is None:
            return None
        for key, value in fields.items():
            setattr(item, key, value)
        await self._session.flush()
        return item

    async def touch_last_used(self, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
        item = await self.get(user_id, item_id)
        if item is not None:
            item.last_used_at = datetime.now(UTC)

    async def delete(self, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
        item = await self.get(user_id, item_id)
        if item is None:
            return False
        await self._session.delete(item)
        return True

    async def hybrid_search(
        self,
        user_id: uuid.UUID,
        *,
        lexical_query: str,
        query_embedding: list[float] | None,
        filters: SearchFilter | None,
        weights: SearchWeights,
        limit: int,
        min_score: float,
    ) -> list[ScoredItem]:
        """Hybrid ranking: 0.55*semantic + 0.25*lexical + 0.10*metadata + 0.10*recency
        (weights configurable). Semantic requires an embedding; if none is
        available (embedding provider unavailable) it degrades to lexical-only.
        """
        tsquery = func.plainto_tsquery("simple", lexical_query) if lexical_query else None

        lexical_raw: Any = (
            func.ts_rank(SavedItem.search_vector, tsquery)
            if tsquery is not None
            else cast(0.0, Float)
        )
        lexical_score = func.least(1.0, lexical_raw * 4.0)

        semantic_score: Any
        if query_embedding is not None:
            cosine_distance = SavedItem.embedding.cosine_distance(query_embedding)
            semantic_score = func.greatest(0.0, 1.0 - cosine_distance)
        else:
            semantic_score = cast(0.0, Float)

        age_days = func.extract(
            "epoch",
            func.now() - func.coalesce(SavedItem.last_used_at, SavedItem.created_at),
        ) / 86400.0
        recency_score = func.pow(0.5, age_days / 30.0)

        # Soft metadata boost: tags/location aren't hard filters (AI parsing of
        # free-text location may not exactly match), they nudge ranking instead.
        metadata_hits: list[Any] = []
        if filters and filters.tags:
            for tag in filters.tags:
                metadata_hits.append(SavedItem.searchable_text.ilike(f"%{tag}%"))
        if filters and filters.location:
            metadata_hits.append(SavedItem.searchable_text.ilike(f"%{filters.location}%"))

        metadata_score: Any
        if metadata_hits:
            metadata_score = case((or_(*metadata_hits), 1.0), else_=0.3)
        else:
            metadata_score = cast(1.0, Float)

        final_score = (
            weights.semantic * semantic_score
            + weights.lexical * lexical_score
            + weights.metadata * metadata_score
            + weights.recency * recency_score
        )

        stmt = select(
            SavedItem,
            final_score.label("final_score"),
            semantic_score.label("semantic_score"),
            lexical_score.label("lexical_score"),
            metadata_score.label("metadata_score"),
            recency_score.label("recency_score"),
        ).where(SavedItem.user_id == user_id, SavedItem.processing_status == "completed")

        conditions = []
        if tsquery is not None and query_embedding is not None:
            conditions.append(
                or_(
                    SavedItem.search_vector.op("@@")(tsquery),
                    SavedItem.embedding.isnot(None),
                )
            )
        if filters:
            if filters.category:
                conditions.append(SavedItem.category == filters.category.value)
            if filters.platform:
                conditions.append(SavedItem.platform == filters.platform.value)
            if filters.favorites_only:
                conditions.append(SavedItem.is_favorite.is_(True))
            if filters.subcategory:
                conditions.append(SavedItem.subcategory == filters.subcategory)
            if filters.date_from:
                parsed_from = _try_parse_date(filters.date_from)
                if parsed_from:
                    conditions.append(SavedItem.created_at >= parsed_from)
            if filters.date_to:
                parsed_to = _try_parse_date(filters.date_to)
                if parsed_to:
                    conditions.append(SavedItem.created_at <= parsed_to)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        if filters and filters.collection_id:
            try:
                collection_uuid = uuid.UUID(filters.collection_id)
            except ValueError:
                collection_uuid = None
            if collection_uuid:
                stmt = (
                    stmt.join(CollectionItem, CollectionItem.saved_item_id == SavedItem.id)
                    .join(Collection, Collection.id == CollectionItem.collection_id)
                    .where(Collection.id == collection_uuid, Collection.user_id == user_id)
                )

        stmt = stmt.order_by(final_score.desc()).limit(limit)

        rows = (await self._session.execute(stmt)).all()
        results = [
            ScoredItem(
                item=row.SavedItem,
                score=float(row.final_score),
                semantic_score=float(row.semantic_score),
                lexical_score=float(row.lexical_score),
                metadata_score=float(row.metadata_score),
                recency_score=float(row.recency_score),
            )
            for row in rows
        ]
        return [r for r in results if r.score >= min_score]
