"""In-memory fakes of Accounts' ports, so use cases can be tested without a database::

    uow, clock = FakeUnitOfWork(), FakeClock()
    await VerifyEmail(uow, clock)(token)
    assert uow.committed

Like ``common_security.testing``: for tests only, never used by the running service.
"""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from accounts.domain.email import Email
from accounts.domain.errors import EmailTakenError
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken
from events import EventPayload

FIXED_NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


class FakeClock:
    """A clock that only moves when a test sets ``current``."""

    __test__ = False  # not a pytest test class

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakePasswordHasher:
    """Fast and predictable, and like a real hash it never contains the password."""

    def hash(self, password: str) -> str:
        return "fake$" + hashlib.sha256(password.encode()).hexdigest()

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == self.hash(password)


class FakeUsers:
    """Stores copies, like a database: changing a User does nothing until ``save``."""

    def __init__(self) -> None:
        self.rows: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        if any(existing.email == user.email for existing in self.rows.values()):
            raise EmailTakenError("An account with this email already exists")
        self.rows[user.id] = replace(user)

    async def get(self, user_id: UUID) -> User | None:
        user = self.rows.get(user_id)
        return replace(user) if user else None

    async def get_by_email(self, email: Email) -> User | None:
        found = [user for user in self.rows.values() if user.email == email]
        return replace(found[0]) if found else None

    async def save(self, user: User) -> None:
        self.rows[user.id] = replace(user)


class FakeVerificationTokens:
    def __init__(self) -> None:
        self.rows: dict[UUID, VerificationToken] = {}

    async def add(self, token: VerificationToken) -> None:
        self.rows[token.id] = replace(token)

    async def get_by_hash(self, token_hash: str) -> VerificationToken | None:
        found = [token for token in self.rows.values() if token.token_hash == token_hash]
        return replace(found[0]) if found else None

    async def save(self, token: VerificationToken) -> None:
        self.rows[token.id] = replace(token)

    async def consume_active_for_user(self, user_id: UUID, now: datetime) -> None:
        for token in self.rows.values():
            if token.user_id == user_id and token.consumed_at is None:
                token.consumed_at = now


class FakeEvents:
    def __init__(self) -> None:
        self.published: list[EventPayload] = []

    async def publish(self, event: EventPayload) -> None:
        self.published.append(event)


class FakeUnitOfWork:
    """Records whether the use case committed. Changes aren't rolled back on failure, so
    tests check ``committed`` instead."""

    def __init__(self) -> None:
        self.users = FakeUsers()
        self.verification_tokens = FakeVerificationTokens()
        self.events = FakeEvents()
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True
