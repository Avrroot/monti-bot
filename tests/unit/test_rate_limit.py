from __future__ import annotations

import uuid

import pytest
from app.services.security import rate_limit
from fakeredis import aioredis as fakeredis_aioredis


@pytest.fixture
async def redis():
    client = fakeredis_aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_user_message_rate_limit_allows_up_to_limit(redis, monkeypatch) -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("RATE_LIMIT_USER_PER_MINUTE", "3")
    get_settings.cache_clear()

    user_id = uuid.uuid4()
    results = [await rate_limit.check_user_message_rate(redis, user_id) for _ in range(4)]

    get_settings.cache_clear()
    monkeypatch.delenv("RATE_LIMIT_USER_PER_MINUTE", raising=False)
    get_settings.cache_clear()

    assert results == [True, True, True, False]


async def test_duplicate_submission_guard_blocks_immediate_repeat(redis) -> None:
    user_id = uuid.uuid4()
    first = await rate_limit.check_duplicate_submission(redis, user_id, "https://example.com/x")
    second = await rate_limit.check_duplicate_submission(redis, user_id, "https://example.com/x")
    assert first is True
    assert second is False


async def test_duplicate_submission_guard_distinguishes_urls(redis) -> None:
    user_id = uuid.uuid4()
    a = await rate_limit.check_duplicate_submission(redis, user_id, "https://example.com/a")
    b = await rate_limit.check_duplicate_submission(redis, user_id, "https://example.com/b")
    assert a is True
    assert b is True


async def test_concurrent_job_limit(redis, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_MAX_CONCURRENT_JOBS_PER_USER", "2")
    get_settings.cache_clear()

    user_id = uuid.uuid4()
    assert await rate_limit.check_concurrent_job_limit(redis, user_id) is True

    await rate_limit.increment_concurrent_jobs(redis, user_id)
    await rate_limit.increment_concurrent_jobs(redis, user_id)
    assert await rate_limit.check_concurrent_job_limit(redis, user_id) is False

    await rate_limit.decrement_concurrent_jobs(redis, user_id)
    assert await rate_limit.check_concurrent_job_limit(redis, user_id) is True

    monkeypatch.delenv("RATE_LIMIT_MAX_CONCURRENT_JOBS_PER_USER", raising=False)
    get_settings.cache_clear()
