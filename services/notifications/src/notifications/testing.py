"""In-memory fakes of Notifications' ports, for tests only (like ``accounts.testing``)."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from notifications.application.ports import ContactsUnavailableError
from notifications.domain.notification_email import Contact
from notifications.domain.notifications import Notification
from notifications.domain.trip_members import TripMember, TripRole
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


class FakeContactDirectory:
    """Contacts from a dict. Set ``unavailable`` to make lookups fail like a down Accounts."""

    def __init__(self, contacts: dict[UUID, Contact] | None = None) -> None:
        self.known = dict(contacts or {})
        self.unavailable = False
        self.asked: list[list[UUID]] = []

    async def contacts(self, user_ids: Sequence[UUID]) -> dict[UUID, Contact]:
        self.asked.append(list(user_ids))
        if self.unavailable:
            raise ContactsUnavailableError("Accounts is down")
        return {user_id: self.known[user_id] for user_id in user_ids if user_id in self.known}


class InMemoryTripMembers:
    """``TripMembers`` in a dict, behaving like the PostgreSQL one."""

    def __init__(self) -> None:
        self.members: dict[tuple[UUID, UUID], TripMember] = {}

    async def add_driver(self, trip_id: UUID, driver_id: UUID) -> None:
        self.members.setdefault(
            (trip_id, driver_id), TripMember(trip_id, driver_id, TripRole.DRIVER)
        )

    async def add_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        self.members[(trip_id, rider_id)] = TripMember(trip_id, rider_id, TripRole.RIDER)

    async def remove_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        member = self.members.get((trip_id, rider_id))
        if member is not None and member.role is TripRole.RIDER:
            self.members[(trip_id, rider_id)] = replace(member, active=False)

    async def end_trip(self, trip_id: UUID) -> None:
        for key, member in list(self.members.items()):
            if member.trip_id == trip_id:
                self.members[key] = replace(member, active=False)

    async def active(self, trip_id: UUID) -> list[TripMember]:
        found = [m for m in self.members.values() if m.trip_id == trip_id and m.active]
        return sorted(found, key=lambda m: (m.role is not TripRole.DRIVER, str(m.user_id)))
