from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.bot.keyboards.callback_data import LanguagePick, SettingsAction
from app.core.logging import get_logger
from app.db.models.user import User
from app.db.repositories.users import UserRepository
from app.services.storage.object_storage import ObjectStorage

logger = get_logger(__name__)
router = Router(name="settings")


def _settings_keyboard(locale: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t("settings.language_button", locale=locale),
            callback_data=SettingsAction(action="language").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=t("settings.delete_data_button", locale=locale),
            callback_data=SettingsAction(action="delete_data").pack(),
        )
    )
    return builder.as_markup()


@router.message(Command("settings"))
async def cmd_settings(message: Message, locale: str) -> None:
    await message.answer(t("settings.title", locale=locale), reply_markup=_settings_keyboard(locale))


@router.callback_query(SettingsAction.filter(F.action == "language"))
async def handle_language_menu(callback: CallbackQuery, locale: str) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Русский", callback_data=LanguagePick(locale="ru").pack()),
        InlineKeyboardButton(text="English", callback_data=LanguagePick(locale="en").pack()),
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("settings.language_choose", locale=locale), reply_markup=builder.as_markup()
        )


@router.callback_query(LanguagePick.filter())
async def handle_language_pick(
    callback: CallbackQuery, callback_data: LanguagePick, session: AsyncSession, user: User
) -> None:
    user.locale = callback_data.locale
    await callback.answer(t("settings.language_saved", locale=callback_data.locale))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("settings.title", locale=callback_data.locale),
            reply_markup=_settings_keyboard(callback_data.locale),
        )


@router.callback_query(SettingsAction.filter(F.action == "delete_data"))
async def handle_delete_data_prompt(callback: CallbackQuery, locale: str) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t("settings.delete_confirm_yes", locale=locale),
            callback_data=SettingsAction(action="delete_confirm_yes").pack(),
        ),
        InlineKeyboardButton(
            text=t("settings.delete_confirm_no", locale=locale),
            callback_data=SettingsAction(action="delete_confirm_no").pack(),
        ),
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("settings.delete_confirm", locale=locale), reply_markup=builder.as_markup()
        )


@router.callback_query(SettingsAction.filter(F.action == "delete_confirm_no"))
async def handle_delete_data_cancel(callback: CallbackQuery, locale: str) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("settings.title", locale=locale), reply_markup=_settings_keyboard(locale)
        )


@router.callback_query(SettingsAction.filter(F.action == "delete_confirm_yes"))
async def handle_delete_data_confirm(
    callback: CallbackQuery, session: AsyncSession, user: User, locale: str
) -> None:
    from sqlalchemy import select

    from app.db.models.saved_item import SavedItem

    storage_keys = (
        await session.execute(
            select(SavedItem.storage_object_key).where(
                SavedItem.user_id == user.id, SavedItem.storage_object_key.isnot(None)
            )
        )
    ).scalars().all()

    repo = UserRepository(session)
    await repo.delete_all_data(user.id)
    await session.flush()

    if storage_keys:
        try:
            await ObjectStorage().delete_many([k for k in storage_keys if k])
        except Exception as exc:  # noqa: BLE001
            logger.warning("delete_data_storage_cleanup_failed", error=str(exc))

    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("settings.delete_done", locale=locale))
