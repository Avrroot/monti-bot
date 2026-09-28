"""Fixed-window rate limiting on Redis (INCR + EXPIRE). Good enough for a
single-bot MVP; swap for a sliding-window/token-bucket algorithm if traffic
grows enough that window-edge bursts become a real problem.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis

from app.core.config import get_settings


async def _allow(redis: Redis, key: str, limit: int, window_seconds: int = 60) -> bool:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    return count <= limit


async def check_user_message_rate(redis: Redis, user_id: uuid.UUID) -> bool:
    settings = get_settings()
    return await _allow(
        redis, f"rl:user:{user_id}", settings.rate_limit_user_per_minute
    )


async def check_extraction_rate(redis: Redis) -> bool:
    settings = get_settings()
    return await _allow(
        redis, "rl:extraction", settings.rate_limit_extraction_per_minute
    )


async def check_ai_rate(redis: Redis) -> bool:
    settings = get_settings()
    return await _allow(redis, "rl:ai", settings.rate_limit_ai_per_minute)


async def check_duplicate_submission(redis: Redis, user_id: uuid.UUID, canonical_url: str) -> bool:
    """Guards against a user double-tapping "send" on the same link within a
    few seconds before the first save has even been created yet.
    """
    key = f"rl:submit:{user_id}:{hash(canonical_url)}"
    is_new = await redis.set(key, "1", ex=10, nx=True)
    return bool(is_new)


async def increment_concurrent_jobs(redis: Redis, user_id: uuid.UUID) -> int:
    return await redis.incr(f"rl:concurrent:{user_id}")


async def decrement_concurrent_jobs(redis: Redis, user_id: uuid.UUID) -> None:
    key = f"rl:concurrent:{user_id}"
    value = await redis.decr(key)
    if value <= 0:
        await redis.delete(key)


async def check_concurrent_job_limit(redis: Redis, user_id: uuid.UUID) -> bool:
    settings = get_settings()
    current = await redis.get(f"rl:concurrent:{user_id}")
    current_int = int(current) if current else 0
    return current_int < settings.rate_limit_max_concurrent_jobs_per_user
