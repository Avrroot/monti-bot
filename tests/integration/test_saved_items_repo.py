from __future__ import annotations

import uuid

import pytest
from app.core.config import SearchWeights
from app.db.models.enums import ProcessingStatus
from app.db.repositories.saved_items import SavedItemRepository
from app.db.repositories.users import UserRepository

pytestmark = pytest.mark.integration


async def _make_user(session, telegram_id: int):
    repo = UserRepository(session)
    return await repo.get_or_create(
        telegram_user_id=telegram_id, username=f"user{telegram_id}", first_name="Test", locale="ru"
    )


async def test_duplicate_detection_by_canonical_url(db_session):
    user = await _make_user(db_session, 1001)
    items = SavedItemRepository(db_session)

    await items.create(
        user_id=user.id,
        url="https://example.com/reel/1",
        canonical_url="https://example.com/reel/1",
        platform="instagram",
    )
    await db_session.flush()

    existing = await items.get_by_canonical_url(user.id, "https://example.com/reel/1")
    assert existing is not None

    missing = await items.get_by_canonical_url(user.id, "https://example.com/reel/2")
    assert missing is None


async def test_user_scoping_isolation(db_session):
    user_a = await _make_user(db_session, 2001)
    user_b = await _make_user(db_session, 2002)
    items = SavedItemRepository(db_session)

    item_a = await items.create(
        user_id=user_a.id,
        url="https://a.example.com",
        canonical_url="https://a.example.com",
        platform="web",
    )
    await db_session.flush()

    # user_b must never be able to fetch user_a's item, even by exact id.
    fetched_by_b = await items.get(user_b.id, item_a.id)
    assert fetched_by_b is None

    fetched_by_a = await items.get(user_a.id, item_a.id)
    assert fetched_by_a is not None

    # user_b's recent list must not include user_a's items.
    recent_b = await items.list_recent(user_b.id)
    assert all(i.id != item_a.id for i in recent_b)


async def test_favorite_toggle_is_scoped_to_owner(db_session):
    user_a = await _make_user(db_session, 3001)
    user_b = await _make_user(db_session, 3002)
    items = SavedItemRepository(db_session)

    item = await items.create(
        user_id=user_a.id,
        url="https://a.example.com/x",
        canonical_url="https://a.example.com/x",
        platform="web",
    )
    await db_session.flush()

    result = await items.set_favorite(user_b.id, item.id, True)
    assert result is None  # user_b cannot favorite user_a's item

    result = await items.set_favorite(user_a.id, item.id, True)
    assert result is not None
    assert result.is_favorite is True


async def test_delete_is_scoped_to_owner(db_session):
    user_a = await _make_user(db_session, 4001)
    user_b = await _make_user(db_session, 4002)
    items = SavedItemRepository(db_session)

    item = await items.create(
        user_id=user_a.id,
        url="https://a.example.com/y",
        canonical_url="https://a.example.com/y",
        platform="web",
    )
    await db_session.flush()

    deleted = await items.delete(user_b.id, item.id)
    assert deleted is False

    deleted = await items.delete(user_a.id, item.id)
    assert deleted is True


async def test_hybrid_search_lexical_match_without_embedding(db_session):
    user = await _make_user(db_session, 5001)
    items = SavedItemRepository(db_session)

    pasta = await items.create(
        user_id=user.id,
        url="https://example.com/pasta",
        canonical_url="https://example.com/pasta",
        platform="web",
        title="Паста карбонара",
        summary="Быстрый рецепт классической карбонары",
        searchable_text="паста карбонара рецепт быстрый ужин",
        category="recipes",
        processing_status=ProcessingStatus.COMPLETED,
    )
    gym = await items.create(
        user_id=user.id,
        url="https://example.com/gym",
        canonical_url="https://example.com/gym",
        platform="web",
        title="Тренировка на пресс",
        summary="Силовая тренировка дома",
        searchable_text="тренировка пресс фитнес дома",
        category="fitness",
        processing_status=ProcessingStatus.COMPLETED,
    )
    await db_session.flush()

    results = await items.hybrid_search(
        user.id,
        lexical_query="паста карбонара",
        query_embedding=None,
        filters=None,
        weights=SearchWeights(),
        limit=10,
        min_score=0.0,
    )

    result_ids = [r.item.id for r in results]
    assert pasta.id in result_ids
    # the pasta item should outrank the unrelated gym item for this query
    pasta_rank = result_ids.index(pasta.id)
    if gym.id in result_ids:
        assert pasta_rank < result_ids.index(gym.id)


async def test_hybrid_search_respects_user_scoping(db_session):
    user_a = await _make_user(db_session, 6001)
    user_b = await _make_user(db_session, 6002)
    items = SavedItemRepository(db_session)

    await items.create(
        user_id=user_a.id,
        url="https://example.com/secret",
        canonical_url="https://example.com/secret",
        platform="web",
        title="Секретный рецепт",
        searchable_text="секретный рецепт",
        processing_status=ProcessingStatus.COMPLETED,
    )
    await db_session.flush()

    results = await items.hybrid_search(
        user_b.id,
        lexical_query="секретный рецепт",
        query_embedding=None,
        filters=None,
        weights=SearchWeights(),
        limit=10,
        min_score=0.0,
    )
    assert results == []


async def test_get_by_id_returns_none_for_random_id(db_session):
    user = await _make_user(db_session, 7001)
    items = SavedItemRepository(db_session)
    assert await items.get(user.id, uuid.uuid4()) is None
