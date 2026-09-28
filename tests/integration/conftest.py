from __future__ import annotations

import os
import subprocess
import sys

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

_TABLES = (
    "usage_events",
    "processing_jobs",
    "collection_items",
    "collections",
    "saved_item_tags",
    "tags",
    "saved_items",
    "user_settings",
    "users",
)


def _run_migrations() -> None:
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not apply migrations to test database: {result.stderr[-2000:]}")


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    try:
        _run_migrations()
    except FileNotFoundError:
        pytest.skip("alembic not available")
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))

    async with factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()
