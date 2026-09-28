"""i18n string tables. Handlers must never hardcode user-facing text — always
go through `t(key, locale=..., **kwargs)` so adding a language later doesn't
require touching every handler.
"""

from __future__ import annotations

RU: dict[str, str] = {
    "start.welcome": (
        "Привет 👋\n\n"
        "Я превращаю ссылки и скриншоты в твою личную библиотеку.\n\n"
        "Отправь мне:\n\n"
        "🎬 Reel / TikTok / Short\n"
        "📌 Pinterest / Threads\n"
        "🔗 любую ссылку\n"
        "🖼 скриншот\n\n"
        "Я разберусь, что внутри, и сохраню.\n\n"
        "А потом можешь спросить, например:\n\n"
        "«найди тот ресторан в Париже»"
    ),
    "start.save_first_button": "➕ Сохранить первое",
    "help.text": (
        "Просто отправь мне ссылку или скриншот — я сам разберусь и сохраню.\n\n"
        "Чтобы найти сохранённое, напиши своими словами, что ищешь, например:\n"
        "«найди рецепт пасты» или «покажи избранное».\n\n"
        "Команды:\n"
        "/library — вся библиотека\n"
        "/recent — последние сохранённые\n"
        "/favorites — избранное\n"
        "/collections — коллекции\n"
        "/settings — настройки\n"
        "/stats — статистика"
    ),
    "status.received": "⏳ Изучаю ссылку...",
    "status.extracting": "⏳ Получаю данные...",
    "status.analyzing": "🧠 Разбираюсь, что внутри...",
    "status.indexing": "📚 Добавляю в библиотеку...",
    "status.image_received": "⏳ Смотрю на изображение...",
    "saved.success_title": "✅ Сохранено",
    "saved.source": "Источник",
    "saved.open_original": "Открыть оригинал",
    "saved.failed_partial": (
        "Не получилось полностью разобрать эту ссылку 😕\n"
        "Но я сохранил её, чтобы ты не потерял."
    ),
    "saved.failed_button_retry": "🔄 Попробовать снова",
    "duplicate.warning": "⚠️ Ты уже сохранял это.",
    "duplicate.show_button": "Показать",
    "duplicate.save_anyway_button": "Сохранить ещё раз",
    "button.favorite_on": "⭐ В избранном",
    "button.favorite_off": "☆ В избранное",
    "button.collection": "📁 В коллекцию",
    "button.edit": "✏️ Изменить",
    "button.delete": "🗑 Удалить",
    "button.back": "⬅️ Назад",
    "button.cancel": "Отмена",
    "delete.confirm": "Удалить эту сохранёнку без возможности восстановления?",
    "delete.confirm_yes": "🗑 Да, удалить",
    "delete.confirm_no": "Отмена",
    "delete.done": "Удалено.",
    "favorite.added": "⭐ Добавлено в избранное",
    "favorite.removed": "☆ Убрано из избранного",
    "library.empty": "Пока пусто. Отправь мне ссылку или скриншот — и я сохраню первую запись.",
    "recent.title": "🕓 Последние сохранённые",
    "favorites.title": "⭐ Избранное",
    "favorites.empty": "В избранном пока пусто.",
    "search.results_title": "🔎 Нашёл {count} сохранёнок",
    "search.no_results": (
        "Ничего не нашёл по этому запросу 🤔\n"
        "Попробуй описать другими словами, или отправь мне новую ссылку."
    ),
    "search.page_indicator": "{current}/{total}",
    "collections.title": "📁 Твои коллекции",
    "collections.empty": "Коллекций пока нет.",
    "collections.new_button": "➕ Новая коллекция",
    "collections.ask_name": "Как назовём коллекцию?",
    "collections.created": "Коллекция «{name}» создана.",
    "collections.added_to": "Добавлено в «{name}»",
    "collections.choose_for_item": "В какую коллекцию добавить?",
    "collections.empty_for_item": "Сначала создай коллекцию.",
    "edit.menu_title": "Что изменить?",
    "edit.field_title": "Название",
    "edit.field_category": "Категория",
    "edit.field_tags": "Теги",
    "edit.field_note": "Заметка",
    "edit.field_collections": "Коллекции",
    "edit.ask_title": "Отправь новое название:",
    "edit.ask_tags": "Отправь теги через запятую:",
    "edit.ask_note": "Отправь заметку (например «сходить сюда с Машей»):",
    "edit.saved": "Сохранено ✅",
    "edit.choose_category": "Выбери категорию:",
    "settings.title": "⚙️ Настройки",
    "settings.language_button": "🌐 Язык",
    "settings.delete_data_button": "🗑 Удалить мои данные",
    "settings.delete_confirm": (
        "Это удалит ВСЕ твои сохранёнки, коллекции и настройки без возможности "
        "восстановления. Точно продолжить?"
    ),
    "settings.delete_confirm_yes": "🗑 Да, удалить всё",
    "settings.delete_confirm_no": "Отмена",
    "settings.delete_done": "Все твои данные удалены.",
    "settings.language_choose": "Выбери язык:",
    "settings.language_saved": "Язык обновлён.",
    "stats.title": "📊 Статистика",
    "stats.total": "Всего сохранено: {total}",
    "stats.favorites": "В избранном: {favorites}",
    "stats.collections": "Коллекций: {collections}",
    "stats.by_category": "По категориям:",
    "error.generic": "Что-то пошло не так 😕 Попробуй ещё раз чуть позже.",
    "error.rate_limited": "Слишком много запросов подряд — подожди немного 🙂",
    "error.image_too_large": "Изображение слишком большое, попробуй отправить поменьше.",
    "error.unsupported_message": (
        "Отправь мне ссылку, скриншот, или напиши, что хочешь найти в своей библиотеке."
    ),
    "blocked.message": "Ты заблокирован в этом боте.",
}

EN: dict[str, str] = {
    "start.welcome": (
        "Hi 👋\n\n"
        "I turn links and screenshots into your personal library.\n\n"
        "Send me:\n\n"
        "🎬 Reel / TikTok / Short\n"
        "📌 Pinterest / Threads\n"
        "🔗 any link\n"
        "🖼 a screenshot\n\n"
        "I'll figure out what's inside and save it.\n\n"
        "Later, just ask, e.g.:\n\n"
        "\"find that rooftop restaurant\""
    ),
    "start.save_first_button": "➕ Save your first one",
    "help.text": (
        "Just send me a link or a screenshot — I'll handle the rest.\n\n"
        "To find something, describe it in your own words, e.g. "
        "\"find that pasta recipe\" or \"show favorites\".\n\n"
        "Commands:\n"
        "/library — full library\n"
        "/recent — recently saved\n"
        "/favorites — favorites\n"
        "/collections — collections\n"
        "/settings — settings\n"
        "/stats — stats"
    ),
    "status.received": "⏳ Looking into this link...",
    "status.extracting": "⏳ Fetching data...",
    "status.analyzing": "🧠 Figuring out what's inside...",
    "status.indexing": "📚 Adding to your library...",
    "status.image_received": "⏳ Looking at the image...",
    "saved.success_title": "✅ Saved",
    "saved.source": "Source",
    "saved.open_original": "Open original",
    "saved.failed_partial": (
        "Couldn't fully parse this link 😕\nBut I saved it so you don't lose it."
    ),
    "saved.failed_button_retry": "🔄 Try again",
    "duplicate.warning": "⚠️ You already saved this.",
    "duplicate.show_button": "Show",
    "duplicate.save_anyway_button": "Save again",
    "button.favorite_on": "⭐ Favorited",
    "button.favorite_off": "☆ Favorite",
    "button.collection": "📁 Add to collection",
    "button.edit": "✏️ Edit",
    "button.delete": "🗑 Delete",
    "button.back": "⬅️ Back",
    "button.cancel": "Cancel",
    "delete.confirm": "Delete this item permanently?",
    "delete.confirm_yes": "🗑 Yes, delete",
    "delete.confirm_no": "Cancel",
    "delete.done": "Deleted.",
    "favorite.added": "⭐ Added to favorites",
    "favorite.removed": "☆ Removed from favorites",
    "library.empty": "Nothing here yet. Send me a link or a screenshot to save your first item.",
    "recent.title": "🕓 Recently saved",
    "favorites.title": "⭐ Favorites",
    "favorites.empty": "No favorites yet.",
    "search.results_title": "🔎 Found {count} items",
    "search.no_results": (
        "Couldn't find anything for that 🤔\nTry describing it differently, "
        "or send me a new link."
    ),
    "search.page_indicator": "{current}/{total}",
    "collections.title": "📁 Your collections",
    "collections.empty": "No collections yet.",
    "collections.new_button": "➕ New collection",
    "collections.ask_name": "What should we call it?",
    "collections.created": "Collection \"{name}\" created.",
    "collections.added_to": "Added to \"{name}\"",
    "collections.choose_for_item": "Which collection?",
    "collections.empty_for_item": "Create a collection first.",
    "edit.menu_title": "What do you want to change?",
    "edit.field_title": "Title",
    "edit.field_category": "Category",
    "edit.field_tags": "Tags",
    "edit.field_note": "Note",
    "edit.field_collections": "Collections",
    "edit.ask_title": "Send the new title:",
    "edit.ask_tags": "Send tags, comma-separated:",
    "edit.ask_note": "Send a note (e.g. \"go here with Sarah\"):",
    "edit.saved": "Saved ✅",
    "edit.choose_category": "Choose a category:",
    "settings.title": "⚙️ Settings",
    "settings.language_button": "🌐 Language",
    "settings.delete_data_button": "🗑 Delete my data",
    "settings.delete_confirm": (
        "This deletes ALL your saved items, collections, and settings permanently. Continue?"
    ),
    "settings.delete_confirm_yes": "🗑 Yes, delete everything",
    "settings.delete_confirm_no": "Cancel",
    "settings.delete_done": "All your data has been deleted.",
    "settings.language_choose": "Choose a language:",
    "settings.language_saved": "Language updated.",
    "stats.title": "📊 Stats",
    "stats.total": "Total saved: {total}",
    "stats.favorites": "Favorites: {favorites}",
    "stats.collections": "Collections: {collections}",
    "stats.by_category": "By category:",
    "error.generic": "Something went wrong 😕 Please try again shortly.",
    "error.rate_limited": "Too many requests in a row — please slow down 🙂",
    "error.image_too_large": "That image is too large, try a smaller one.",
    "error.unsupported_message": (
        "Send me a link, a screenshot, or tell me what to look for in your library."
    ),
    "blocked.message": "You are blocked from using this bot.",
}

_LOCALES: dict[str, dict[str, str]] = {"ru": RU, "en": EN}


def t(key: str, locale: str = "ru", **kwargs: object) -> str:
    table = _LOCALES.get(locale, RU)
    template = table.get(key) or RU.get(key) or key
    return template.format(**kwargs) if kwargs else template
