"""Router aggregation. ORDER MATTERS: FSM-state-scoped message handlers
(item_actions, collections) must be included before intake's catch-all text
handler, otherwise the catch-all would swallow replies meant for an
in-progress edit/collection-name prompt.
"""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers import (
    browse,
    collections,
    intake,
    item_actions,
    library,
    settings,
    start,
)


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(library.router)
    root.include_router(collections.router)
    root.include_router(item_actions.router)
    root.include_router(browse.router)
    root.include_router(settings.router)
    root.include_router(intake.router)
    return root
