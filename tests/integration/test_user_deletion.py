from __future__ import annotations

import pytest
from app.db.models.collection import Collection
from app.db.models.saved_item import SavedItem
from app.db.models.tag import Tag
from app.db.models.user import User
from app.db.repositories.collections import CollectionRepository
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.tags import TagRepository
from app.db.repositories.users import UserRepository
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def test_delete_all_data_cascades_everything(db_session):
    users = UserRepository(db_session)
    items = SavedItemRepository(db_session)
    collections = CollectionRepository(db_session)
    tags = TagRepository(db_session)

    user = await users.get_or_create(
        telegram_user_id=9001, username="priv", first_name="Priv", locale="ru"
    )
    item = await items.create(
        user_id=user.id, url="https://x.com/1", canonical_url="https://x.com/1", platform="web"
    )
    await db_session.flush()

    await tags.set_tags_for_item(user.id, item.id, ["тест"])
    await collections.get_or_create_by_name(user.id, "Тест")
    await db_session.flush()

    user_id = user.id
    await users.delete_all_data(user_id)
    await db_session.flush()

    assert (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(SavedItem).where(SavedItem.user_id == user_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Collection).where(Collection.user_id == user_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(Tag).where(Tag.user_id == user_id))
    ).scalar_one_or_none() is None
