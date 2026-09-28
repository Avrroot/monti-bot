from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.i18n import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, locale: str) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=t("start.save_first_button", locale=locale), callback_data="noop")
    )
    await message.answer(t("start.welcome", locale=locale), reply_markup=builder.as_markup())


@router.message(Command("help"))
async def cmd_help(message: Message, locale: str) -> None:
    await message.answer(t("help.text", locale=locale))


@router.callback_query(lambda c: c.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()
