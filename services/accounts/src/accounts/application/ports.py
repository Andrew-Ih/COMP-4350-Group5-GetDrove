"""Ports: the interfaces (``typing.Protocol``) that use cases need from the outside world.

Adapters implement these, and tests use in-memory fakes.
"""

from datetime import datetime, timedelta
from typing import Protocol, Self
from uuid import UUID

from accounts.domain.email import Email
from accounts.domain.refresh_token import RefreshToken
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken
from events import EventPublisher


class Clock(Protocol):
    """The current time. Tests use a fixed clock to check expiry without waiting."""

    def now(self) -> datetime:
        """The current time, timezone-aware, in UTC."""
        ...


class PasswordHasher(Protocol):
    """Turns passwords into one-way hashes and checks them (Argon2id, ADR 0020)."""

    def hash(self, password: str) -> str:
        """A new hash with its own random salt; the same password hashes differently each
        time."""
        ...

    def verify(self, password_hash: str, password: str) -> bool:
        """Whether ``password`` matches ``password_hash``. False for a wrong password or a
        damaged hash; never raises for those."""
        ...

    def verify_dummy(self, password: str) -> None:
        """Takes as long as ``verify`` but checks nothing. Login calls it when there's no
        account, so response times don't reveal which emails are registered."""
        ...


class AccessTokenIssuer(Protocol):
    """Makes the short-lived access token other services check (ADR 0006)."""

    @property
    def lifetime(self) -> timedelta:
        """How long a token is valid (15 minutes); sent to the client as ``expiresIn``."""
        ...

    def issue(self, user: User, now: datetime) -> str:
        """A signed token for ``user``, valid from ``now`` for ``lifetime``."""
        ...


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

    async def save(self, user: User) -> None:
        """Saves changes to an existing user, e.g. that their email is now verified."""
        ...


class VerificationTokenRepository(Protocol):
    """Email verification tokens. Only hashes are stored. Implementations never commit."""

    async def add(self, token: VerificationToken) -> None:
        """Saves a new token."""
        ...

    async def get_by_hash(self, token_hash: str) -> VerificationToken | None:
        """The token with this hash, or None. Locked until the transaction ends, so two
        clicks on the same link at once can't both use it."""
        ...

    async def save(self, token: VerificationToken) -> None:
        """Saves changes to a token, i.e. that it was used."""
        ...

    async def consume_active_for_user(self, user_id: UUID, now: datetime) -> None:
        """Marks all of the user's unused tokens as used, so older links stop working
        when a new one is sent."""
        ...


class RefreshTokenRepository(Protocol):
    """Refresh ("stay logged in") tokens. Only hashes are stored. Implementations never
    commit."""

    async def add(self, token: RefreshToken) -> None:
        """Saves a new token."""
        ...

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """The token with this hash, or None. Locked until the transaction ends, so the
        same token can't be swapped twice at once."""
        ...


class UnitOfWork(Protocol):
    """One use case's database work: the repositories and the event publisher share one
    transaction, so changes and the events about them are saved together or not at all.

    Use it as ``async with uow: ... await uow.commit()``. Leaving the block without
    committing (returning early or raising) rolls everything back.
    """

    @property
    def users(self) -> UserRepository: ...

    @property
    def verification_tokens(self) -> VerificationTokenRepository: ...

    @property
    def refresh_tokens(self) -> RefreshTokenRepository: ...

    @property
    def events(self) -> EventPublisher: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, *exc_info: object) -> None: ...

    async def commit(self) -> None: ...
