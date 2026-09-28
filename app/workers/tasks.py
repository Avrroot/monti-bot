"""arq job bodies. Kept thin: open a session, run the pipeline, render+edit
the Telegram status message, done. Pipeline-level failures (extraction/AI/
embedding) are already handled gracefully inside process_url_save /
process_image_save and never raise — only infrastructure failures (DB/Redis
down) propagate out of here, which is exactly what should trigger arq's
retry-with-backoff.
"""

from __future__ import annotations

import uuid

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from arq import Retry

from app.bot.i18n import t
from app.bot.rendering import item_card_keyboard, render_item_card
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.db.repositories.tags import TagRepository
from app.db.session import async_session_factory
from app.services.content.pipeline import process_image_save, process_url_save
from app.services.security.rate_limit import decrement_concurrent_jobs
from app.services.storage.factory import get_object_storage

logger = get_logger(__name__)

MAX_TRIES = 5


async def _safe_edit(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            logger.warning("edit_message_failed", error=str(exc))


def _backoff_or_raise(ctx: dict, exc: Exception) -> None:
    job_try = ctx.get("job_try", 1)
    logger.error("worker_job_failed", job_try=job_try, error=str(exc))
    if job_try >= MAX_TRIES:
        raise exc
    raise Retry(defer=min(60, 2**job_try))


async def save_url_task(
    ctx: dict,
    *,
    user_id: str,
    saved_item_id: str,
    raw_url: str,
    chat_id: int,
    status_message_id: int,
    locale: str = "ru",
) -> None:
    bot: Bot = ctx["bot"]
    await _safe_edit(bot, chat_id, status_message_id, t("status.extracting", locale=locale))

    try:
        async with async_session_factory() as session:
            try:
                item = await process_url_save(
                    session,
                    user_id=uuid.UUID(user_id),
                    saved_item_id=uuid.UUID(saved_item_id),
                    raw_url=raw_url,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

            if item is None:
                return

            tags_repo = TagRepository(session)
            tags = await tags_repo.list_for_item(item.id)
    except Exception as exc:  # noqa: BLE001 - infra failure, let arq retry
        _backoff_or_raise(ctx, exc)
        return

    text = render_item_card(item, tags, locale=locale)
    keyboard = item_card_keyboard(item, locale=locale)
    await _safe_edit(
        bot, chat_id, status_message_id, text, reply_markup=keyboard, parse_mode="HTML"
    )

    redis = get_redis()
    await decrement_concurrent_jobs(redis, uuid.UUID(user_id))


async def save_image_task(
    ctx: dict,
    *,
    user_id: str,
    saved_item_id: str,
    storage_key: str,
    mime_type: str,
    caption: str | None,
    chat_id: int,
    status_message_id: int,
    locale: str = "ru",
) -> None:
    bot: Bot = ctx["bot"]
    await _safe_edit(bot, chat_id, status_message_id, t("status.analyzing", locale=locale))

    try:
        storage = get_object_storage()
        image_bytes = await storage.get_bytes(storage_key)

        async with async_session_factory() as session:
            try:
                item = await process_image_save(
                    session,
                    user_id=uuid.UUID(user_id),
                    saved_item_id=uuid.UUID(saved_item_id),
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    caption=caption,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

            if item is None:
                return

            tags_repo = TagRepository(session)
            tags = await tags_repo.list_for_item(item.id)
    except Exception as exc:  # noqa: BLE001
        _backoff_or_raise(ctx, exc)
        return

    text = render_item_card(item, tags, locale=locale)
    keyboard = item_card_keyboard(item, locale=locale)
    await _safe_edit(
        bot, chat_id, status_message_id, text, reply_markup=keyboard, parse_mode="HTML"
    )

    redis = get_redis()
    await decrement_concurrent_jobs(redis, uuid.UUID(user_id))
