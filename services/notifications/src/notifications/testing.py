"""In-memory fakes of Notifications' ports, for tests only (like ``accounts.testing``)."""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from notifications.domain.notifications import Notification
from notifications.domain.verification_email import EmailMessage


class FakeEmailSender:
    """Keeps sent emails in ``sent``. Set ``fail_with`` to make the next sends raise."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    async def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)


class InMemoryNotificationStore:
    """``NotificationStore`` in a dict, behaving like the PostgreSQL one."""

    def __init__(self, *notifications: Notification) -> None:
        self.notifications = {item.id: item for item in notifications}

    async def add(self, notification: Notification) -> None:
        self.notifications[notification.id] = notification

    async def latest(self, user_id: UUID, limit: int) -> list[Notification]:
        mine = [item for item in self.notifications.values() if item.user_id == user_id]
        mine.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return mine[:limit]

    async def unread_count(self, user_id: UUID) -> int:
        return sum(
            1
            for item in self.notifications.values()
            if item.user_id == user_id and item.read_at is None
        )

    async def mark_read(self, user_id: UUID, notification_id: UUID, at: datetime) -> bool:
        item = self.notifications.get(notification_id)
        if item is None or item.user_id != user_id:
            return False
        if item.read_at is None:
            self.notifications[notification_id] = replace(item, read_at=at)
        return True

    async def mark_all_read(self, user_id: UUID, at: datetime) -> None:
        for item in list(self.notifications.values()):
            if item.user_id == user_id and item.read_at is None:
                self.notifications[item.id] = replace(item, read_at=at)
