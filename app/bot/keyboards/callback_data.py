from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class ItemAction(CallbackData, prefix="item"):
    action: str  # fav_on, fav_off, edit, delete, collection, open_from_search
    item_id: str


class DeleteConfirm(CallbackData, prefix="delc"):
    item_id: str
    confirm: str  # yes, no


class DuplicateAction(CallbackData, prefix="dup"):
    action: str  # show, save_anyway
    item_id: str


class CollectionPick(CallbackData, prefix="colpick"):
    item_id: str
    collection_id: str


class CollectionsMenu(CallbackData, prefix="colmenu"):
    action: str  # new, open, back
    collection_id: str = ""


class EditMenu(CallbackData, prefix="editm"):
    item_id: str
    field: str  # title, category, tags, note, collections, back


class EditCategoryPick(CallbackData, prefix="editcat"):
    item_id: str
    category: str


class SearchNav(CallbackData, prefix="spage"):
    direction: str  # prev, next
    page: int


class SettingsAction(CallbackData, prefix="settings"):
    action: str  # language, delete_data, delete_confirm_yes, delete_confirm_no


class LanguagePick(CallbackData, prefix="lang"):
    locale: str

