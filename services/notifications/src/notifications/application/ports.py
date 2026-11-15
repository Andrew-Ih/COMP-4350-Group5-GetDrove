"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from typing import Protocol
from uuid import UUID

from notifications.domain.reminders import TripReminder
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
