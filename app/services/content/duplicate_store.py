"""Remembers the raw URL behind a duplicate-warning prompt so the "Save
again" button can re-trigger processing without re-sending the link.
Keyed by (user_id, existing_item_id) since that pair is what's encoded in
the callback_data's 64-byte budget.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis

_TTL_SECONDS = 10 * 60


def _key(user_id: uuid.UUID, existing_item_id: uuid.UUID) -> str:
    return f"dup_pending:{user_id}:{existing_item_id}"


async def save_pending_url(
    redis: Redis, user_id: uuid.UUID, existing_item_id: uuid.UUID, raw_url: str
) -> None:
    await redis.set(_key(user_id, existing_item_id), raw_url, ex=_TTL_SECONDS)


async def get_pending_url(
    redis: Redis, user_id: uuid.UUID, existing_item_id: uuid.UUID
) -> str | None:
    return await redis.get(_key(user_id, existing_item_id))
