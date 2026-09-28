from __future__ import annotations

from aiogram import Bot
from arq.connections import RedisSettings

from app.bot.factory import build_bot
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.workers.tasks import save_image_task, save_url_task

logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    configure_logging()
    settings = get_settings()
    ctx["bot"] = build_bot(settings)
    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    bot: Bot | None = ctx.get("bot")
    if bot is not None:
        await bot.session.close()
    logger.info("worker_stopped")


class WorkerSettings:
    functions = [save_url_task, save_image_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 120
    max_tries = 5
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
