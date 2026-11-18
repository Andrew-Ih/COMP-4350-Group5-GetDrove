"""An ``EmailSender`` that never emails certain addresses (#415).

The demo accounts (``getdrove.demo.*@myumanitoba.ca``, #111) are made-up addresses. On the
live site, every email to them would go through Brevo and bounce, which hurts our sender's
reputation. Production lists them in ``NOTIFICATIONS_EMAIL_SKIP_PATTERNS``; this wraps the
real sender and drops their emails. The in-app notification is made before the email is
sent, so the bell still works for them in a demo.
"""

import logging
from collections.abc import Sequence
from fnmatch import fnmatchcase

from notifications.application.ports import EmailSender
from notifications.domain.verification_email import EmailMessage

logger = logging.getLogger(__name__)


class SkipAddresses:
    def __init__(self, sender: EmailSender, patterns: Sequence[str]) -> None:
        self._sender = sender
        # Addresses aren't case-sensitive in practice, so neither is matching.
        self._patterns = [pattern.strip().lower() for pattern in patterns if pattern.strip()]

    def skips(self, address: str) -> bool:
        """Whether ``address`` matches a pattern (``*`` is any text, ``?`` one character)."""
        address = address.strip().lower()
        return any(fnmatchcase(address, pattern) for pattern in self._patterns)

    async def send(self, message: EmailMessage) -> None:
        if self.skips(message.to):
            # Not the address: logs never hold anyone's email.
            logger.info("Email not sent: the address is on the skip list (%s)", message.subject)
            return
        await self._sender.send(message)


def skip_addresses(sender: EmailSender, patterns: Sequence[str]) -> EmailSender:
    """``sender`` itself when nothing is skipped (local development), otherwise wrapped."""
    return SkipAddresses(sender, patterns) if any(p.strip() for p in patterns) else sender
