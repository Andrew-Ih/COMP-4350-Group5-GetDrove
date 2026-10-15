"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from typing import Protocol
from uuid import UUID

from accounts.domain.email import Email
from accounts.domain.user import User


class UserRepository(Protocol):
    """Saves and finds accounts. Implementations never commit; the use case does."""

    async def add(self, user: User) -> None:
        """Saves a new user. Raises ``EmailTakenError`` if the email is already used."""
        ...

    async def get(self, user_id: UUID) -> User | None:
        """The user with this ID, or None."""
        ...

    async def get_by_email(self, email: Email) -> User | None:
        """The user with this email, or None."""
        ...
