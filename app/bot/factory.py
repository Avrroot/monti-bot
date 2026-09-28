"""Shared aiogram Bot construction, used by both the bot process (main.py)
and the worker process (workers/worker.py needs its own Bot instance to edit
status messages) — kept in one place so proxy wiring doesn't drift between
the two.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from app.core.config import Settings


def build_bot(settings: Settings) -> Bot:
    """Routes Telegram Bot API calls through PROXY_URL when set -- needed on
    VPS networks that can't reach api.telegram.org directly. Requires the
    `aiohttp-socks` package for socks5:// proxies (aiogram raises a clear
    ImportError pointing at it otherwise). Must be plain `socks5://`, not
    `socks5h://` -- aiohttp-socks rejects the `h` suffix (it always resolves
    DNS through the proxy regardless, so nothing is lost).
    """
    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
        session=session,
    )
