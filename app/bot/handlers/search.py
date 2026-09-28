from __future__ import annotations

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.browse import send_browse_page
from app.bot.i18n import t
from app.db.models.user import User
from app.services.search.search_service import search_library


async def handle_search_query(
    message: Message, session: AsyncSession, user: User, locale: str, query_text: str
) -> None:
    results = await search_library(session, user_id=user.id, query_text=query_text)
    items = [r.item for r in results]

    header = (
        t("search.results_title", locale=locale, count=len(items)) if len(items) > 1 else None
    )
    await send_browse_page(
        message,
        session,
        user,
        locale,
        items=items,
        header=header,
        empty_text=t("search.no_results", locale=locale),
    )
