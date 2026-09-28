from __future__ import annotations

import asyncio

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.factory import build_bot
from app.bot.handlers import build_root_router
from app.bot.middlewares.db_session import DbSessionMiddleware
from app.bot.middlewares.logging import ErrorHandlingMiddleware, LoggingMiddleware
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.bot.middlewares.user_context import UserContextMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.queue import close_arq_pool
from app.services.storage.object_storage import ObjectStorage

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()
    settings = get_settings()

    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, traces_sample_rate=0.1)

    bot = build_bot(settings)
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    # Outermost first: catch anything unhandled -> bind request context -> open
    # a DB session -> resolve/authenticate the user -> rate-limit.
    dp.update.outer_middleware(ErrorHandlingMiddleware())
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(UserContextMiddleware())
    dp.update.outer_middleware(RateLimitMiddleware())

    dp.include_router(build_root_router())

    try:
        await ObjectStorage().ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("object_storage_bootstrap_failed", error=str(exc))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("bot_starting")
        await dp.start_polling(bot)
    finally:
        await close_arq_pool()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
