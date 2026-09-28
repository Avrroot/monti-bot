from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserSettings


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, telegram_user_id: int, username: str | None, first_name: str | None, locale: str
    ) -> User:
        user = await self.get_by_telegram_id(telegram_user_id)
        if user is not None:
            user.last_active_at = datetime.now(UTC)
            if username is not None:
                user.telegram_username = username
            return user

        user = User(
            telegram_user_id=telegram_user_id,
            telegram_username=username,
            first_name=first_name,
            locale=locale,
            last_active_at=datetime.now(UTC),
        )
        self._session.add(user)
        await self._session.flush()

        self._session.add(UserSettings(user_id=user.id, locale=locale))
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def delete_all_data(self, user_id: uuid.UUID) -> None:
        """Cascade delete via FK ON DELETE CASCADE covers saved_items,
        collections, tags, processing_jobs, usage_events, user_settings.
        """
        user = await self._session.get(User, user_id)
        if user is not None:
            await self._session.delete(user)
