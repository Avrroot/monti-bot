from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.bot.i18n import t
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.services.security.rate_limit import check_user_message_rate

logger = get_logger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is None:
            return await handler(event, data)

        redis = get_redis()
        allowed = await check_user_message_rate(redis, user.id)
        if not allowed:
            logger.info("rate_limited", user_id=str(user.id))
            if isinstance(event, Message):
                locale = data.get("locale", "ru")
                await event.answer(t("error.rate_limited", locale=locale))
            return None

        return await handler(event, data)
