"""The bell's use cases (#145), with an in-memory store."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from notifications.application.notification_bell import (
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from notifications.domain.errors import NotificationNotFoundError
from notifications.domain.notifications import Notification, NotificationType
from notifications.testing import InMemoryNotificationStore

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
ME, SOMEONE_ELSE = uuid4(), uuid4()


def notification(
    user_id: UUID = ME, minutes_ago: int = 0, read_at: datetime | None = None
) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.REQUEST_ACCEPTED,
        title="Request accepted",
        body="Maya accepted your request for Monday at 7:45 AM.",
        created_at=NOW - timedelta(minutes=minutes_ago),
        trip_id=uuid4(),
        request_id=uuid4(),
        read_at=read_at,
    )


async def test_lists_my_notifications_newest_first() -> None:
    old, new = notification(minutes_ago=10), notification(minutes_ago=1)
    store = InMemoryNotificationStore(old, new, notification(SOMEONE_ELSE))

    page = await ListNotifications(store).execute(user_id=ME, limit=30)

    assert [item.id for item in page.items] == [new.id, old.id]
    assert page.unread_count == 2


async def test_the_unread_count_covers_more_than_the_page() -> None:
    store = InMemoryNotificationStore(*(notification(minutes_ago=i) for i in range(5)))

    page = await ListNotifications(store).execute(user_id=ME, limit=2)

    assert len(page.items) == 2
    assert page.unread_count == 5


async def test_read_notifications_arent_counted_as_unread() -> None:
    store = InMemoryNotificationStore(notification(), notification(read_at=NOW))

    page = await ListNotifications(store).execute(user_id=ME, limit=30)

    assert page.unread_count == 1


async def test_marking_one_as_read() -> None:
    item = notification()
    store = InMemoryNotificationStore(item)

    await MarkNotificationRead(store, clock=lambda: NOW).execute(
        user_id=ME, notification_id=item.id
    )

    assert store.notifications[item.id].read_at == NOW


async def test_marking_one_as_read_again_keeps_the_first_read_time() -> None:
    first_read = NOW - timedelta(hours=1)
    item = notification(read_at=first_read)
    store = InMemoryNotificationStore(item)

    await MarkNotificationRead(store, clock=lambda: NOW).execute(
        user_id=ME, notification_id=item.id
    )

    assert store.notifications[item.id].read_at == first_read


async def test_someone_elses_notification_is_not_found() -> None:
    theirs = notification(SOMEONE_ELSE)
    store = InMemoryNotificationStore(theirs)

    with pytest.raises(NotificationNotFoundError):
        await MarkNotificationRead(store).execute(user_id=ME, notification_id=theirs.id)

    assert store.notifications[theirs.id].read_at is None


async def test_a_missing_notification_is_not_found() -> None:
    with pytest.raises(NotificationNotFoundError):
        await MarkNotificationRead(InMemoryNotificationStore()).execute(
            user_id=ME, notification_id=uuid4()
        )


async def test_marking_all_as_read_only_touches_mine() -> None:
    mine, theirs = notification(), notification(SOMEONE_ELSE)
    store = InMemoryNotificationStore(mine, theirs)

    await MarkAllNotificationsRead(store, clock=lambda: NOW).execute(user_id=ME)

    assert store.notifications[mine.id].read_at == NOW
    assert store.notifications[theirs.id].read_at is None
