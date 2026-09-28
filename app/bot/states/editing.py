from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class EditItemStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_tags = State()
    waiting_for_note = State()


class CollectionStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_name_for_item = State()
