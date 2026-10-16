"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from typing import Protocol

from notifications.domain.verification_email import EmailMessage


class EmailSender(Protocol):
    """Delivers an email (Mailpit locally, Brevo in production; ADR 0010)."""

    async def send(self, message: EmailMessage) -> None:
        """Sends ``message``. Raises if it couldn't be handed to the mail server, so the
        event is retried later."""
        ...
