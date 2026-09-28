from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.collection import Collection, CollectionItem


class CollectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[Collection]:
        stmt = (
            select(Collection)
            .where(Collection.user_id == user_id)
            .order_by(Collection.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars())

    async def get(self, user_id: uuid.UUID, collection_id: uuid.UUID) -> Collection | None:
        stmt = select(Collection).where(
            Collection.id == collection_id, Collection.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_or_create_by_name(self, user_id: uuid.UUID, name: str) -> Collection:
        name = name.strip()
        stmt = select(Collection).where(Collection.user_id == user_id, Collection.name == name)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
        collection = Collection(user_id=user_id, name=name)
        self._session.add(collection)
        await self._session.flush()
        return collection

    async def add_item(
        self, user_id: uuid.UUID, collection_id: uuid.UUID, saved_item_id: uuid.UUID
    ) -> bool:
        collection = await self.get(user_id, collection_id)
        if collection is None:
            return False
        stmt = pg_insert(CollectionItem).values(
            collection_id=collection_id, saved_item_id=saved_item_id
        )
        await self._session.execute(
            stmt.on_conflict_do_nothing(index_elements=["collection_id", "saved_item_id"])
        )
        return True

    async def remove_item(
        self, user_id: uuid.UUID, collection_id: uuid.UUID, saved_item_id: uuid.UUID
    ) -> None:
        collection = await self.get(user_id, collection_id)
        if collection is None:
            return
        await self._session.execute(
            delete(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.saved_item_id == saved_item_id,
            )
        )

    async def list_item_ids(self, user_id: uuid.UUID, collection_id: uuid.UUID) -> list[uuid.UUID]:
        collection = await self.get(user_id, collection_id)
        if collection is None:
            return []
        stmt = select(CollectionItem.saved_item_id).where(
            CollectionItem.collection_id == collection_id
        )
        return [row[0] for row in (await self._session.execute(stmt)).all()]

    async def list_for_item(self, saved_item_id: uuid.UUID) -> list[Collection]:
        stmt = (
            select(Collection)
            .join(CollectionItem, CollectionItem.collection_id == Collection.id)
            .where(CollectionItem.saved_item_id == saved_item_id)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def counts_for_user(self, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
        stmt = (
            select(CollectionItem.collection_id, func.count(CollectionItem.saved_item_id))
            .join(Collection, Collection.id == CollectionItem.collection_id)
            .where(Collection.user_id == user_id)
            .group_by(CollectionItem.collection_id)
        )
        return dict((await self._session.execute(stmt)).all())

    async def delete(self, user_id: uuid.UUID, collection_id: uuid.UUID) -> bool:
        collection = await self.get(user_id, collection_id)
        if collection is None:
            return False
        await self._session.delete(collection)
        return True
