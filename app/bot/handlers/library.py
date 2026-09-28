from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.browse import send_browse_page
from app.bot.i18n import t
from app.db.models.enums import CATEGORY_EMOJI, Category
from app.db.models.user import User
from app.db.repositories.collections import CollectionRepository
from app.db.repositories.saved_items import SavedItemRepository

router = Router(name="library")

_RECENT_LIMIT = 20
_FAVORITES_LIMIT = 20


@router.message(Command("recent"))
async def cmd_recent(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    items_repo = SavedItemRepository(session)
    items = await items_repo.list_recent(user.id, limit=_RECENT_LIMIT)
    await send_browse_page(
        message,
        session,
        user,
        locale,
        items=items,
        header=t("recent.title", locale=locale),
        empty_text=t("library.empty", locale=locale),
    )


@router.message(Command("library"))
async def cmd_library(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    items_repo = SavedItemRepository(session)
    items = await items_repo.list_recent(user.id, limit=_RECENT_LIMIT)
    await send_browse_page(
        message,
        session,
        user,
        locale,
        items=items,
        header=None,
        empty_text=t("library.empty", locale=locale),
    )


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    items_repo = SavedItemRepository(session)
    items = await items_repo.list_favorites(user.id, limit=_FAVORITES_LIMIT)
    await send_browse_page(
        message,
        session,
        user,
        locale,
        items=items,
        header=t("favorites.title", locale=locale),
        empty_text=t("favorites.empty", locale=locale),
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    items_repo = SavedItemRepository(session)
    collections_repo = CollectionRepository(session)

    total = await items_repo.count_for_user(user.id)
    favorites = await items_repo.list_favorites(user.id, limit=10_000)
    collections = await collections_repo.list_for_user(user.id)
    by_category = await items_repo.counts_by_category(user.id)

    lines = [
        t("stats.title", locale=locale),
        "",
        t("stats.total", locale=locale, total=total),
        t("stats.favorites", locale=locale, favorites=len(favorites)),
        t("stats.collections", locale=locale, collections=len(collections)),
    ]

    if by_category:
        lines.append("")
        lines.append(t("stats.by_category", locale=locale))
        for category, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
            if not category:
                continue
            try:
                emoji = CATEGORY_EMOJI.get(Category(category), "📌")
            except ValueError:
                emoji = "📌"
            lines.append(f"{emoji} {category.replace('_', ' ').title()}: {count}")

    await message.answer("\n".join(lines))
