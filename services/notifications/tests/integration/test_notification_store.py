"""``SQLAlchemyNotificationStore`` (#145) against a real PostgreSQL, with the migrations
applied: what the bell reads and changes, limited to one user."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.notification_store import SQLAlchemyNotificationStore
from notifications.adapters.persistence.tables import notifications
from notifications.domain.notifications import Notification, NotificationType

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
ME, SOMEONE_ELSE = uuid4(), uuid4()


def notification(user_id: UUID = ME, minutes_ago: int = 0) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.TRIP_CANCELLED,
        title="Trip cancelled",
        body="Maya cancelled Monday's trip to campus.",
        created_at=NOW - timedelta(minutes=minutes_ago),
        trip_id=uuid4(),
    )


async def test_saves_and_reads_back_every_field(session: AsyncSession) -> None:
    store = SQLAlchemyNotificationStore(session)
    item = notification()

    await store.add(item)
    [saved] = await store.latest(ME, 30)

    assert saved == item


async def test_latest_is_mine_newest_first_and_limited(session: AsyncSession) -> None:
    store = SQLAlchemyNotificationStore(session)
    items = [notification(minutes_ago=minutes) for minutes in (30, 10, 20)]
    for item in items:
        await store.add(item)
    await store.add(notification(SOMEONE_ELSE))

    latest = await store.latest(ME, 2)

    assert [item.id for item in latest] == [items[1].id, items[2].id]


async def test_unread_count_and_marking_read(session: AsyncSession) -> None:
    store = SQLAlchemyNotificationStore(session)
    first, second = notification(), notification(minutes_ago=1)
    for item in (first, second, notification(SOMEONE_ELSE)):
        await store.add(item)

    assert await store.unread_count(ME) == 2
    assert await store.mark_read(ME, first.id, NOW) is True
    assert await store.unread_count(ME) == 1

    # Marking it again keeps the first read time.
    assert await store.mark_read(ME, first.id, NOW + timedelta(hours=1)) is True
    [read] = [item for item in await store.latest(ME, 30) if item.id == first.id]
    assert read.read_at == NOW


async def test_cant_mark_someone_elses_or_a_missing_notification(session: AsyncSession) -> None:
    store = SQLAlchemyNotificationStore(session)
    theirs = notification(SOMEONE_ELSE)
    await store.add(theirs)

    assert await store.mark_read(ME, theirs.id, NOW) is False
    assert await store.mark_read(ME, uuid4(), NOW) is False
    assert await store.unread_count(SOMEONE_ELSE) == 1


async def test_mark_all_read_only_touches_my_unread_ones(session: AsyncSession) -> None:
    store = SQLAlchemyNotificationStore(session)
    already_read = notification(minutes_ago=5)
    await store.add(already_read)
    await store.mark_read(ME, already_read.id, NOW - timedelta(hours=1))
    await store.add(notification())
    await store.add(notification(SOMEONE_ELSE))

    await store.mark_all_read(ME, NOW)

    assert await store.unread_count(ME) == 0
    assert await store.unread_count(SOMEONE_ELSE) == 1
    [kept] = [item for item in await store.latest(ME, 30) if item.id == already_read.id]
    assert kept.read_at == NOW - timedelta(hours=1)


async def test_the_database_rejects_an_unknown_type(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(
            notifications.insert().values(
                id=uuid4(),
                user_id=ME,
                type="something_else",
                title="?",
                body="?",
                created_at=NOW,
            )
        )
    await session.rollback()


async def test_the_unread_count_has_an_index_of_unread_rows_only(session: AsyncSession) -> None:
    """The bell polls the unread count every few seconds; a partial index means the count
    only reads unread rows, however many old notifications a user has."""
    definition = await session.scalar(
        text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = 'notifications' "
            "AND indexname = 'ix_notifications_unread_user_id'"
        )
    )

    assert definition is not None
    assert "(user_id)" in definition
    assert "WHERE (read_at IS NULL)" in definition
