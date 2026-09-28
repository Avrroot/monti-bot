from __future__ import annotations

import pytest
from app.db.repositories.collections import CollectionRepository
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.users import UserRepository

pytestmark = pytest.mark.integration


async def _make_user(session, telegram_id: int):
    repo = UserRepository(session)
    return await repo.get_or_create(
        telegram_user_id=telegram_id, username=None, first_name="Test", locale="ru"
    )


async def test_collection_add_and_list_item(db_session):
    user = await _make_user(db_session, 8001)
    items = SavedItemRepository(db_session)
    collections = CollectionRepository(db_session)

    item = await items.create(
        user_id=user.id, url="https://x.com/1", canonical_url="https://x.com/1", platform="web"
    )
    collection = await collections.get_or_create_by_name(user.id, "Париж")
    await db_session.flush()

    added = await collections.add_item(user.id, collection.id, item.id)
    assert added is True

    item_ids = await collections.list_item_ids(user.id, collection.id)
    assert item.id in item_ids

    item_collections = await collections.list_for_item(item.id)
    assert any(c.id == collection.id for c in item_collections)


async def test_collection_is_scoped_to_owner(db_session):
    user_a = await _make_user(db_session, 8101)
    user_b = await _make_user(db_session, 8102)
    collections = CollectionRepository(db_session)

    collection = await collections.get_or_create_by_name(user_a.id, "Рецепты")
    await db_session.flush()

    fetched_by_b = await collections.get(user_b.id, collection.id)
    assert fetched_by_b is None

    deleted_by_b = await collections.delete(user_b.id, collection.id)
    assert deleted_by_b is False


async def test_get_or_create_by_name_is_idempotent(db_session):
    user = await _make_user(db_session, 8201)
    collections = CollectionRepository(db_session)

    first = await collections.get_or_create_by_name(user.id, "Хочу купить")
    await db_session.flush()
    second = await collections.get_or_create_by_name(user.id, "Хочу купить")

    assert first.id == second.id
