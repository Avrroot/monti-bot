from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.bot.keyboards.callback_data import CollectionPick, CollectionsMenu, ItemAction
from app.bot.states.editing import CollectionStates
from app.db.models.user import User
from app.db.repositories.collections import CollectionRepository

router = Router(name="collections")


@router.message(Command("collections"))
async def cmd_collections(message: Message, session: AsyncSession, user: User, locale: str) -> None:
    repo = CollectionRepository(session)
    collections = await repo.list_for_user(user.id)
    counts = await repo.counts_for_user(user.id)

    builder = InlineKeyboardBuilder()
    for collection in collections:
        count = counts.get(collection.id, 0)
        builder.button(
            text=f"📁 {collection.name} ({count})",
            callback_data=CollectionsMenu(action="open", collection_id=str(collection.id)),
        )
    builder.button(
        text=t("collections.new_button", locale=locale),
        callback_data=CollectionsMenu(action="new"),
    )
    builder.adjust(1)

    title = t("collections.title", locale=locale) if collections else t(
        "collections.empty", locale=locale
    )
    await message.answer(title, reply_markup=builder.as_markup())


@router.callback_query(CollectionsMenu.filter(F.action == "new"))
async def handle_new_collection_prompt(callback: CallbackQuery, state: FSMContext, locale: str) -> None:
    await state.set_state(CollectionStates.waiting_for_name)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(t("collections.ask_name", locale=locale))


@router.message(CollectionStates.waiting_for_name)
async def handle_new_collection_name(
    message: Message, state: FSMContext, session: AsyncSession, user: User, locale: str
) -> None:
    await state.clear()
    name = (message.text or "").strip()[:128]
    if not name:
        return
    repo = CollectionRepository(session)
    collection = await repo.get_or_create_by_name(user.id, name)
    await message.answer(t("collections.created", locale=locale, name=collection.name))


@router.callback_query(ItemAction.filter(F.action == "collection"))
async def handle_pick_collection_for_item(
    callback: CallbackQuery, callback_data: ItemAction, session: AsyncSession, user: User, locale: str
) -> None:
    repo = CollectionRepository(session)
    collections = await repo.list_for_user(user.id)

    builder = InlineKeyboardBuilder()
    for collection in collections:
        builder.button(
            text=f"📁 {collection.name}",
            callback_data=CollectionPick(
                item_id=callback_data.item_id, collection_id=str(collection.id)
            ),
        )
    builder.button(
        text=t("collections.new_button", locale=locale),
        callback_data=CollectionsMenu(action="new"),
    )
    builder.adjust(1)

    text = (
        t("collections.choose_for_item", locale=locale)
        if collections
        else t("collections.empty_for_item", locale=locale)
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(CollectionPick.filter())
async def handle_collection_pick(
    callback: CallbackQuery, callback_data: CollectionPick, session: AsyncSession, user: User, locale: str
) -> None:
    repo = CollectionRepository(session)
    collection = await repo.get(user.id, uuid.UUID(callback_data.collection_id))
    if collection is None:
        await callback.answer()
        return

    await repo.add_item(user.id, collection.id, uuid.UUID(callback_data.item_id))
    await callback.answer(t("collections.added_to", locale=locale, name=collection.name))
