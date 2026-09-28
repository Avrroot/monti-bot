from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.bot.keyboards.callback_data import DeleteConfirm, EditCategoryPick, EditMenu, ItemAction
from app.bot.rendering import item_card_keyboard, render_item_card
from app.bot.states.editing import EditItemStates
from app.core.logging import get_logger
from app.db.models.enums import CATEGORY_EMOJI, Category
from app.db.models.user import User
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.services.content.searchable_text import rebuild_searchable_text_for_item
from app.services.storage.factory import get_object_storage

logger = get_logger(__name__)
router = Router(name="item_actions")


async def _refresh_card(
    callback: CallbackQuery, session: AsyncSession, user: User, locale: str, item_id: uuid.UUID
) -> None:
    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, item_id)
    if item is None or not isinstance(callback.message, Message):
        return
    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    text = render_item_card(item, tags, locale=locale)
    keyboard = item_card_keyboard(item, locale=locale)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(ItemAction.filter(F.action.in_({"fav_on", "fav_off"})))
async def handle_favorite_toggle(
    callback: CallbackQuery,
    callback_data: ItemAction,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    items_repo = SavedItemRepository(session)
    item_id = uuid.UUID(callback_data.item_id)
    is_favorite = callback_data.action == "fav_on"
    item = await items_repo.set_favorite(user.id, item_id, is_favorite)
    if item is None:
        await callback.answer()
        return

    await callback.answer(
        t("favorite.added" if is_favorite else "favorite.removed", locale=locale)
    )
    await _refresh_card(callback, session, user, locale, item_id)


@router.callback_query(ItemAction.filter(F.action == "delete"))
async def handle_delete_prompt(
    callback: CallbackQuery, callback_data: ItemAction, locale: str
) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t("delete.confirm_yes", locale=locale),
            callback_data=DeleteConfirm(item_id=callback_data.item_id, confirm="yes").pack(),
        ),
        InlineKeyboardButton(
            text=t("delete.confirm_no", locale=locale),
            callback_data=DeleteConfirm(item_id=callback_data.item_id, confirm="no").pack(),
        ),
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            t("delete.confirm", locale=locale), reply_markup=builder.as_markup()
        )


@router.callback_query(DeleteConfirm.filter(F.confirm == "no"))
async def handle_delete_cancel(callback: CallbackQuery, locale: str) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.delete()


@router.callback_query(DeleteConfirm.filter(F.confirm == "yes"))
async def handle_delete_confirm(
    callback: CallbackQuery,
    callback_data: DeleteConfirm,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    items_repo = SavedItemRepository(session)
    item_id = uuid.UUID(callback_data.item_id)
    item = await items_repo.get(user.id, item_id)
    storage_key = item.storage_object_key if item else None

    deleted = await items_repo.delete(user.id, item_id)

    if deleted and storage_key:
        try:
            await get_object_storage().delete(storage_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("delete_storage_object_failed", key=storage_key, error=str(exc))

    await callback.answer(t("delete.done", locale=locale))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("delete.done", locale=locale))


@router.callback_query(ItemAction.filter(F.action == "edit"))
async def handle_edit_menu(
    callback: CallbackQuery, callback_data: ItemAction, locale: str
) -> None:
    item_id = callback_data.item_id
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t("edit.field_title", locale=locale),
            callback_data=EditMenu(item_id=item_id, field="title").pack(),
        ),
        InlineKeyboardButton(
            text=t("edit.field_category", locale=locale),
            callback_data=EditMenu(item_id=item_id, field="category").pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=t("edit.field_tags", locale=locale),
            callback_data=EditMenu(item_id=item_id, field="tags").pack(),
        ),
        InlineKeyboardButton(
            text=t("edit.field_note", locale=locale),
            callback_data=EditMenu(item_id=item_id, field="note").pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=t("button.back", locale=locale),
            callback_data=EditMenu(item_id=item_id, field="back").pack(),
        )
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("edit.menu_title", locale=locale), reply_markup=builder.as_markup()
        )


@router.callback_query(EditMenu.filter(F.field == "back"))
async def handle_edit_back(
    callback: CallbackQuery, callback_data: EditMenu, session: AsyncSession, user: User, locale: str
) -> None:
    await callback.answer()
    await _refresh_card(callback, session, user, locale, uuid.UUID(callback_data.item_id))


@router.callback_query(EditMenu.filter(F.field == "category"))
async def handle_edit_category_menu(
    callback: CallbackQuery, callback_data: EditMenu, locale: str
) -> None:
    builder = InlineKeyboardBuilder()
    for category in Category:
        emoji = CATEGORY_EMOJI.get(category, "📌")
        label = category.value.replace("_", " ").title()
        builder.button(
            text=f"{emoji} {label}",
            callback_data=EditCategoryPick(item_id=callback_data.item_id, category=category.value),
        )
    builder.adjust(2)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("edit.choose_category", locale=locale), reply_markup=builder.as_markup()
        )


@router.callback_query(EditCategoryPick.filter())
async def handle_edit_category_pick(
    callback: CallbackQuery,
    callback_data: EditCategoryPick,
    session: AsyncSession,
    user: User,
    locale: str,
) -> None:
    items_repo = SavedItemRepository(session)
    item_id = uuid.UUID(callback_data.item_id)
    item = await items_repo.get(user.id, item_id)
    if item is None:
        await callback.answer()
        return

    item.category = callback_data.category
    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    item.searchable_text = rebuild_searchable_text_for_item(item, tags)

    await callback.answer(t("edit.saved", locale=locale))
    await _refresh_card(callback, session, user, locale, item_id)


@router.callback_query(EditMenu.filter(F.field.in_({"title", "tags", "note"})))
async def handle_edit_field_prompt(
    callback: CallbackQuery, callback_data: EditMenu, state: FSMContext, locale: str
) -> None:
    prompts = {
        "title": ("edit.ask_title", EditItemStates.waiting_for_title),
        "tags": ("edit.ask_tags", EditItemStates.waiting_for_tags),
        "note": ("edit.ask_note", EditItemStates.waiting_for_note),
    }
    prompt_key, fsm_state = prompts[callback_data.field]
    await state.set_state(fsm_state)
    await state.update_data(item_id=callback_data.item_id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(t(prompt_key, locale=locale))


@router.message(EditItemStates.waiting_for_title)
async def handle_edit_title_input(
    message: Message, state: FSMContext, session: AsyncSession, user: User, locale: str
) -> None:
    data = await state.get_data()
    item_id = uuid.UUID(data["item_id"])
    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, item_id)
    await state.clear()
    if item is None:
        return

    item.title = (message.text or "").strip()[:500]
    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    item.searchable_text = rebuild_searchable_text_for_item(item, tags)

    await message.answer(t("edit.saved", locale=locale))
    text = render_item_card(item, tags, locale=locale)
    await message.answer(text, reply_markup=item_card_keyboard(item, locale=locale), parse_mode="HTML")


@router.message(EditItemStates.waiting_for_tags)
async def handle_edit_tags_input(
    message: Message, state: FSMContext, session: AsyncSession, user: User, locale: str
) -> None:
    data = await state.get_data()
    item_id = uuid.UUID(data["item_id"])
    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, item_id)
    await state.clear()
    if item is None:
        return

    names = [n.strip() for n in (message.text or "").split(",") if n.strip()]
    tags_repo = TagRepository(session)
    await tags_repo.set_tags_for_item(user.id, item.id, names)
    tags = await tags_repo.list_for_item(item.id)
    item.searchable_text = rebuild_searchable_text_for_item(item, tags)

    await message.answer(t("edit.saved", locale=locale))
    text = render_item_card(item, tags, locale=locale)
    await message.answer(text, reply_markup=item_card_keyboard(item, locale=locale), parse_mode="HTML")


@router.message(EditItemStates.waiting_for_note)
async def handle_edit_note_input(
    message: Message, state: FSMContext, session: AsyncSession, user: User, locale: str
) -> None:
    data = await state.get_data()
    item_id = uuid.UUID(data["item_id"])
    items_repo = SavedItemRepository(session)
    item = await items_repo.get(user.id, item_id)
    await state.clear()
    if item is None:
        return

    item.user_note = (message.text or "").strip()[:2000]
    tags_repo = TagRepository(session)
    tags = await tags_repo.list_for_item(item.id)
    item.searchable_text = rebuild_searchable_text_for_item(item, tags)

    await message.answer(t("edit.saved", locale=locale))
    text = render_item_card(item, tags, locale=locale)
    await message.answer(text, reply_markup=item_card_keyboard(item, locale=locale), parse_mode="HTML")
