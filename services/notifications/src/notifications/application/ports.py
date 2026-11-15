"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from notifications.domain.notification_email import Contact
from notifications.domain.notifications import Notification
from notifications.domain.reminders import TripReminder
from notifications.domain.trip_members import TripMember
from notifications.domain.verification_email import EmailMessage


class EmailSender(Protocol):
    """Delivers an email (Mailpit locally, Brevo in production; ADR 0010)."""

    async def send(self, message: EmailMessage) -> None:
        """Sends ``message``. Raises if it couldn't be handed to the mail server, so the
        event is retried later."""
        ...


class ReminderStore(Protocol):
    """Keeps trip reminders (#148) until the scheduler sends them (#149)."""

    async def add(self, reminder: TripReminder) -> bool:
        """Stores ``reminder``. Returns False, and changes nothing, if its request already
        has a reminder: a repeated ``RequestAccepted`` never creates a second one."""
        ...

    async def cancel_for_request(self, request_id: UUID) -> int:
        """Cancels the request's pending reminder. Returns how many were cancelled."""
        ...

    async def cancel_for_trip(self, trip_id: UUID) -> int:
        """Cancels every pending reminder on the trip. Returns how many were cancelled."""
        ...


class NotificationStore(Protocol):
    """Keeps in-app notifications (#145). Every read and update is limited to one user."""

    async def add(self, notification: Notification) -> None:
        """Saves a new notification. Event handlers call this inside the transaction that
        records the event, so a repeated event doesn't add a second one."""
        ...

    async def latest(self, user_id: UUID, limit: int) -> list[Notification]:
        """The user's ``limit`` newest notifications, newest first."""
        ...

    async def unread_count(self, user_id: UUID) -> int:
        """How many of the user's notifications are unread (all of them, not just the
        latest)."""
        ...

    async def mark_read(self, user_id: UUID, notification_id: UUID, at: datetime) -> bool:
        """Marks one of the user's notifications as read at ``at``; one already read keeps
        its first read time. Returns False if the user has no notification with this ID."""
        ...

    async def mark_all_read(self, user_id: UUID, at: datetime) -> None:
        """Marks all of the user's unread notifications as read at ``at``."""
        ...


class ContactsUnavailableError(Exception):
    """Accounts couldn't say where to send emails. The event is retried later, so nobody
    misses their email."""


class ContactDirectory(Protocol):
    """Names and emails, from Accounts (#146). Events carry only user IDs."""

    async def contacts(self, user_ids: Sequence[UUID]) -> dict[UUID, Contact]:
        """The contacts of these users, by ID. Unknown users are left out. Raises
        ``ContactsUnavailableError`` if Accounts can't be asked."""
        ...


class TripMembers(Protocol):
    """Who is on each trip (#146), kept in step with Trips' events: the driver, and riders
    with a seat. For messages to everyone on a trip, and later the trip chat (#61, #63)."""

    async def add_driver(self, trip_id: UUID, driver_id: UUID) -> None:
        """Records the trip's driver. Doing it again changes nothing."""
        ...

    async def add_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        """Records an accepted rider, or puts one back who had left."""
        ...

    async def remove_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        """The rider cancelled or was removed. They stay listed, as no longer active."""
        ...

    async def end_trip(self, trip_id: UUID) -> None:
        """The trip was cancelled: nobody is active on it any more."""
        ...

    async def active(self, trip_id: UUID) -> list[TripMember]:
        """Everyone still on the trip, driver first."""
        ...
