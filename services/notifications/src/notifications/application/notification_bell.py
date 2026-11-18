"""Use cases behind the bell (#145): list my notifications, mark one or all as read."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from notifications.application.ports import NotificationStore
from notifications.domain.errors import NotificationNotFoundError
from notifications.domain.notifications import NotificationPage

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class ListNotifications:
    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    async def execute(self, *, user_id: UUID, limit: int) -> NotificationPage:
        return NotificationPage(
            items=await self._store.latest(user_id, limit),
            unread_count=await self._store.unread_count(user_id),
        )


class MarkNotificationRead:
    def __init__(self, store: NotificationStore, clock: Clock = utc_now) -> None:
        self._store = store
        self._clock = clock

    async def execute(self, *, user_id: UUID, notification_id: UUID) -> None:
        """Raises ``NotificationNotFoundError`` if the user has no notification with this
        ID. Marking one that is already read again is fine."""
        if not await self._store.mark_read(user_id, notification_id, self._clock()):
            raise NotificationNotFoundError


class MarkAllNotificationsRead:
    def __init__(self, store: NotificationStore, clock: Clock = utc_now) -> None:
        self._store = store
        self._clock = clock

    async def execute(self, *, user_id: UUID) -> None:
        await self._store.mark_all_read(user_id, self._clock())
