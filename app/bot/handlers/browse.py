"""Shared pagination helpers for any "browse a list of saved items one card
at a time" flow: search results, /recent, /favorites, /library. All of them
stash an ordered list of item ids in Redis (session_store) and page through
full item cards via the same ⬅️ N/M ➡️ control.
"""

from __future__ import annotations

import uuid

from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.callback_data import SearchNav
from app.bot.rendering import item_card_keyboard, render_item_card
from app.core.redis import get_redis
from app.db.models.saved_item import SavedItem
from app.db.models.user import User
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.services.search.session_store import get_search_session, save_search_session

router = Router(name="browse")


async def send_browse_page(
    message: Message,
    session: AsyncSession,
    user: User,
    locale: str,
    *,
    items: list[SavedItem],
    header: str | None,
    empty_text: str,
) -> None:
    if not items:
        await message.answer(empty_text)
        return

    redis = get_redis()
    await save_search_session(redis, user.id, [str(i.id) for i in items])

    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(items[0].id)

    text = render_item_card(items[0], tags, locale=locale)
    if header and len(items) > 1:
        text = f"{header}\n\n{text}"

    keyboard = item_card_keyboard(
        items[0], locale=locale, with_search_nav=len(items) > 1, page=0, total=len(items)
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(SearchNav.filter())
async def handle_browse_nav(
    callback: CallbackQuery,
    callback_data: SearchNav,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    redis = get_redis()
    item_ids = await get_search_session(redis, user.id)
    if not item_ids:
        await callback.answer()
        return

    total = len(item_ids)
    page = callback_data.page
    page = page - 1 if callback_data.direction == "prev" else page + 1
    page = max(0, min(page, total - 1))

    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, uuid.UUID(item_ids[page]))
    if item is None:
        await callback.answer()
        return

    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    text = render_item_card(item, tags, locale=locale)
    keyboard = item_card_keyboard(item, locale=locale, with_search_nav=True, page=page, total=total)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
