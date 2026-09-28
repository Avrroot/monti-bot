from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tag import SavedItemTag, Tag


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_many(self, user_id: uuid.UUID, names: list[str]) -> list[Tag]:
        normalized = {n.strip().lower() for n in names if n.strip()}
        if not normalized:
            return []

        existing_stmt = select(Tag).where(Tag.user_id == user_id, Tag.name.in_(normalized))
        existing = {t.name: t for t in (await self._session.execute(existing_stmt)).scalars()}

        missing = normalized - existing.keys()
        for name in missing:
            tag = Tag(user_id=user_id, name=name)
            self._session.add(tag)
            existing[name] = tag

        if missing:
            await self._session.flush()

        return list(existing.values())

    async def set_tags_for_item(
        self, user_id: uuid.UUID, saved_item_id: uuid.UUID, names: list[str]
    ) -> None:
        tags = await self.get_or_create_many(user_id, names)

        await self._session.execute(
            delete(SavedItemTag).where(SavedItemTag.saved_item_id == saved_item_id)
        )
        if not tags:
            return

        stmt = pg_insert(SavedItemTag).values(
            [{"saved_item_id": saved_item_id, "tag_id": tag.id} for tag in tags]
        )
        await self._session.execute(stmt.on_conflict_do_nothing())

    async def list_for_item(self, saved_item_id: uuid.UUID) -> list[str]:
        stmt = (
            select(Tag.name)
            .join(SavedItemTag, SavedItemTag.tag_id == Tag.id)
            .where(SavedItemTag.saved_item_id == saved_item_id)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_for_items(
        self, saved_item_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[str]]:
        if not saved_item_ids:
            return {}
        stmt = select(SavedItemTag.saved_item_id, Tag.name).join(
            Tag, Tag.id == SavedItemTag.tag_id
        ).where(SavedItemTag.saved_item_id.in_(saved_item_ids))
        result = await self._session.execute(stmt)
        out: dict[uuid.UUID, list[str]] = {}
        for item_id, name in result.all():
            out.setdefault(item_id, []).append(name)
        return out
