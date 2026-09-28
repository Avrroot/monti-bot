"""Short-lived Redis-backed storage for the current search result set, so
inline pagination buttons (which have a strict 64-byte callback_data limit)
can page through a saved list of item ids instead of re-running search.
One active search session per user; a new search overwrites the old one.
"""

from __future__ import annotations

import json
import uuid

from redis.asyncio import Redis

_TTL_SECONDS = 30 * 60


def _key(user_id: uuid.UUID) -> str:
    return f"search_session:{user_id}"


async def save_search_session(redis: Redis, user_id: uuid.UUID, item_ids: list[str]) -> None:
    await redis.set(_key(user_id), json.dumps(item_ids), ex=_TTL_SECONDS)


async def get_search_session(redis: Redis, user_id: uuid.UUID) -> list[str] | None:
    raw = await redis.get(_key(user_id))
    if raw is None:
        return None
    return json.loads(raw)
