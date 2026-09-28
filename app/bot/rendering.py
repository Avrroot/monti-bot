"""Turns SavedItem rows into Telegram card text + inline keyboards.

Centralized here so the worker (which edits the status message when
processing finishes) and the bot handlers (search results, /recent,
/favorites, favorite toggles) render identical cards.
"""

from __future__ import annotations

from html import escape as h

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import t
from app.bot.keyboards.callback_data import DuplicateAction, ItemAction, SearchNav
from app.db.models.enums import CATEGORY_EMOJI, Category, ProcessingStatus
from app.db.models.saved_item import SavedItem

_PLATFORM_LABELS = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "youtube_shorts": "YouTube Shorts",
    "pinterest": "Pinterest",
    "threads": "Threads",
    "web": "Web",
    "telegram_image": "Изображение",
}


def _category_line(category: str | None, subcategory: str | None) -> str | None:
    if not category:
        return None
    try:
        cat_enum = Category(category)
    except ValueError:
        cat_enum = Category.OTHER
    emoji = CATEGORY_EMOJI.get(cat_enum, "📌")
    label = category.replace("_", " ").title()
    line = f"{emoji} {h(label)}"
    if subcategory:
        line += f" → {h(subcategory)}"
    return line


def render_item_card(item: SavedItem, tags: list[str], locale: str = "ru") -> str:
    if item.processing_status == ProcessingStatus.FAILED and not item.title:
        fallback_lines = [t("saved.failed_partial", locale=locale), "", h(item.url)]
        return "\n".join(fallback_lines)

    lines: list[str] = [f"<b>{h(item.title or item.url)}</b>"]

    if item.summary:
        lines.append("")
        lines.append(h(item.summary))

    cat_line = _category_line(item.category, item.subcategory)
    if cat_line:
        lines.append("")
        lines.append(cat_line)

    if tags:
        lines.append("🏷 " + " · ".join(h(tag) for tag in tags))

    if item.user_note:
        lines.append("")
        lines.append(f"📝 {h(item.user_note)}")

    platform_label = _PLATFORM_LABELS.get(item.platform, item.platform)
    lines.append("")
    lines.append(f"{t('saved.source', locale=locale)}: {h(platform_label)}")

    if item.processing_status == ProcessingStatus.FAILED:
        lines.append("")
        lines.append("⚠️ " + t("saved.failed_partial", locale=locale))

    return "\n".join(lines)


def item_card_keyboard(
    item: SavedItem, locale: str = "ru", *, with_search_nav: bool = False, page: int = 0, total: int = 0
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    fav_label = (
        t("button.favorite_on", locale=locale)
        if item.is_favorite
        else t("button.favorite_off", locale=locale)
    )
    fav_action = "fav_off" if item.is_favorite else "fav_on"
    builder.row(
        InlineKeyboardButton(
            text=fav_label,
            callback_data=ItemAction(action=fav_action, item_id=str(item.id)).pack(),
        ),
        InlineKeyboardButton(
            text=t("button.collection", locale=locale),
            callback_data=ItemAction(action="collection", item_id=str(item.id)).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=t("button.edit", locale=locale),
            callback_data=ItemAction(action="edit", item_id=str(item.id)).pack(),
        ),
        InlineKeyboardButton(
            text=t("button.delete", locale=locale),
            callback_data=ItemAction(action="delete", item_id=str(item.id)).pack(),
        ),
    )
    if item.url:
        builder.row(
            InlineKeyboardButton(text=t("saved.open_original", locale=locale), url=item.url)
        )

    if with_search_nav and total > 1:
        builder.row(
            InlineKeyboardButton(
                text="⬅️", callback_data=SearchNav(direction="prev", page=page).pack()
            ),
            InlineKeyboardButton(
                text=t("search.page_indicator", locale=locale, current=page + 1, total=total),
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="➡️", callback_data=SearchNav(direction="next", page=page).pack()
            ),
        )

    return builder.as_markup()


def duplicate_warning_keyboard(item_id: str, locale: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t("duplicate.show_button", locale=locale),
            callback_data=DuplicateAction(action="show", item_id=item_id).pack(),
        ),
        InlineKeyboardButton(
            text=t("duplicate.save_anyway_button", locale=locale),
            callback_data=DuplicateAction(action="save_anyway", item_id=item_id).pack(),
        ),
    )
    return builder.as_markup()
