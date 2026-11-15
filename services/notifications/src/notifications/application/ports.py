"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from notifications.domain.notifications import Notification
from notifications.domain.verification_email import EmailMessage


class EmailSender(Protocol):
    """Delivers an email (Mailpit locally, Brevo in production; ADR 0010)."""

    async def send(self, message: EmailMessage) -> None:
        """Sends ``message``. Raises if it couldn't be handed to the mail server, so the
        event is retried later."""
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
