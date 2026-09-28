"""Entry point for everything the user sends that isn't a recognized command:
- a message containing a URL -> save pipeline
- a photo / image document -> screenshot pipeline
- anything else text -> treated as a natural-language search query

This is the literal implementation of the product principle: CAPTURE -> the
user never has to pick a mode, the bot figures out intent.
"""

from __future__ import annotations

import io
import uuid

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.search import handle_search_query
from app.bot.i18n import t
from app.bot.keyboards.callback_data import DuplicateAction
from app.bot.rendering import duplicate_warning_keyboard, item_card_keyboard, render_item_card
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.queue import get_arq_pool
from app.core.redis import get_redis
from app.db.models.enums import Platform, ProcessingStatus
from app.db.models.processing_job import ProcessingJob
from app.db.models.user import User
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.services.content.duplicate_store import get_pending_url, save_pending_url
from app.services.content.url_utils import detect_platform, extract_first_url, normalize_url
from app.services.security.rate_limit import (
    check_concurrent_job_limit,
    check_duplicate_submission,
    check_extraction_rate,
    increment_concurrent_jobs,
)
from app.services.security.safe_http import UnsafeURLError, validate_url_safety
from app.services.storage.factory import get_object_storage

logger = get_logger(__name__)
router = Router(name="intake")

_IMAGE_MIME_ALLOWLIST = {"image/jpeg", "image/png", "image/webp"}


async def _start_url_processing(
    message: Message, session: AsyncSession, user: User, locale: str, raw_url: str
) -> None:
    redis = get_redis()

    canonical_url = normalize_url(raw_url)

    try:
        validate_url_safety(canonical_url)
    except UnsafeURLError:
        await message.answer(t("error.generic", locale=locale))
        logger.info("url_rejected_unsafe", url=canonical_url)
        return

    if not await check_duplicate_submission(redis, user.id, canonical_url):
        return  # silently drop rapid double-taps of the same link

    items_repo = SavedItemRepository(session)
    existing = await items_repo.get_by_canonical_url(user.id, canonical_url)
    if existing is not None:
        await save_pending_url(redis, user.id, existing.id, raw_url)
        await message.answer(
            t("duplicate.warning", locale=locale),
            reply_markup=duplicate_warning_keyboard(str(existing.id), locale=locale),
        )
        return

    if not await check_extraction_rate(redis):
        await message.answer(t("error.rate_limited", locale=locale))
        return

    if not await check_concurrent_job_limit(redis, user.id):
        await message.answer(t("error.rate_limited", locale=locale))
        return

    platform = detect_platform(canonical_url)
    item = await items_repo.create(
        user_id=user.id,
        url=raw_url,
        canonical_url=canonical_url,
        platform=platform.value,
        processing_status=ProcessingStatus.PENDING,
    )
    await session.flush()

    status_message = await message.answer(t("status.received", locale=locale))

    idempotency_key = f"save_url:{user.id}:{item.id}"
    job = ProcessingJob(
        user_id=user.id,
        saved_item_id=item.id,
        idempotency_key=idempotency_key,
        job_type="save_url",
        telegram_chat_id=message.chat.id,
        telegram_status_message_id=status_message.message_id,
    )
    session.add(job)
    await session.flush()
    await session.commit()

    await increment_concurrent_jobs(redis, user.id)

    pool = await get_arq_pool()
    await pool.enqueue_job(
        "save_url_task",
        _job_id=idempotency_key,
        user_id=str(user.id),
        saved_item_id=str(item.id),
        raw_url=raw_url,
        chat_id=message.chat.id,
        status_message_id=status_message.message_id,
        locale=locale,
    )


@router.message(F.photo)
async def handle_photo(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    settings = get_settings()
    redis = get_redis()

    if not await check_concurrent_job_limit(redis, user.id):
        await message.answer(t("error.rate_limited", locale=locale))
        return

    if not message.photo or message.bot is None:
        return

    photo = message.photo[-1]
    if photo.file_size and photo.file_size > settings.image_max_bytes:
        await message.answer(t("error.image_too_large", locale=locale))
        return

    buffer = io.BytesIO()
    await message.bot.download(photo, destination=buffer)
    data = buffer.getvalue()
    if len(data) > settings.image_max_bytes:
        await message.answer(t("error.image_too_large", locale=locale))
        return

    mime_type = "image/jpeg"

    status_message = await message.answer(t("status.image_received", locale=locale))

    storage = get_object_storage()
    await storage.ensure_bucket()
    storage_key = await storage.upload_bytes(data, content_type=mime_type)

    items_repo = SavedItemRepository(session)
    item = await items_repo.create(
        user_id=user.id,
        url=f"telegram://photo/{photo.file_unique_id}",
        canonical_url=f"telegram://photo/{photo.file_unique_id}",
        platform=Platform.TELEGRAM_IMAGE.value,
        processing_status=ProcessingStatus.PENDING,
        source_telegram_file_id=photo.file_id,
        storage_object_key=storage_key,
    )
    await session.flush()

    idempotency_key = f"save_image:{user.id}:{item.id}"
    job = ProcessingJob(
        user_id=user.id,
        saved_item_id=item.id,
        idempotency_key=idempotency_key,
        job_type="save_image",
        telegram_chat_id=message.chat.id,
        telegram_status_message_id=status_message.message_id,
    )
    session.add(job)
    await session.flush()
    await session.commit()

    await increment_concurrent_jobs(redis, user.id)

    pool = await get_arq_pool()
    await pool.enqueue_job(
        "save_image_task",
        _job_id=idempotency_key,
        user_id=str(user.id),
        saved_item_id=str(item.id),
        storage_key=storage_key,
        mime_type=mime_type,
        caption=message.caption,
        chat_id=message.chat.id,
        status_message_id=status_message.message_id,
        locale=locale,
    )


@router.callback_query(DuplicateAction.filter(F.action == "show"))
async def handle_duplicate_show(
    callback: CallbackQuery,
    callback_data: DuplicateAction,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, uuid.UUID(callback_data.item_id))
    if item is None:
        await callback.answer()
        return
    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    text = render_item_card(item, tags, locale=locale)
    keyboard = item_card_keyboard(item, locale=locale)
    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(DuplicateAction.filter(F.action == "save_anyway"))
async def handle_duplicate_save_anyway(
    callback: CallbackQuery,
    callback_data: DuplicateAction,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    redis = get_redis()
    raw_url = await get_pending_url(redis, user.id, uuid.UUID(callback_data.item_id))
    await callback.answer()
    if not raw_url or not isinstance(callback.message, Message):
        return
    await _start_url_processing(callback.message, session, user, locale, raw_url)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    url = extract_first_url(text)
    if url:
        await _start_url_processing(message, session, user, locale, url)
        return

    await handle_search_query(message, session, user, locale, text)
