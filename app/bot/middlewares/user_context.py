from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser

from app.core.config import get_settings
from app.db.repositories.users import UserRepository


class UserContextMiddleware(BaseMiddleware):
    """Ensures every update is scoped to a `User` row (creating it on first
    contact) and blocks banned users before any handler runs. This is the
    single choke point that guarantees data['user'] is always the correct,
    authenticated owner for everything downstream (search, saves, deletes).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        settings = get_settings()
        session = data["session"]
        repo = UserRepository(session)
        user = await repo.get_or_create(
            telegram_user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            locale=settings.default_locale,
        )
        await session.flush()

        if user.is_blocked:
            return None

        data["user"] = user
        data["locale"] = user.locale
        return await handler(event, data)
