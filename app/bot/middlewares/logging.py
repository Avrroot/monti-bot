from __future__ import annotations

import contextlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.bot.i18n import t
from app.core.logging import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        request_id = str(uuid.uuid4())
        tg_user = data.get("event_from_user")
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            telegram_user_id=tg_user.id if tg_user else None,
        )
        try:
            return await handler(event, data)
        finally:
            structlog.contextvars.clear_contextvars()


class ErrorHandlingMiddleware(BaseMiddleware):
    """Outermost middleware: never let an unhandled exception reach aiogram's
    default behavior (which would surface a stack trace-adjacent failure to
    the user). Logs full details server-side, replies with a friendly
    message client-side.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("unhandled_update_error")
            if isinstance(event, Message):
                locale = data.get("locale", "ru")
                with contextlib.suppress(Exception):
                    await event.answer(t("error.generic", locale=locale))
            return None
