"""In-memory fakes of Accounts' ports, so use cases can be tested without a database::

    uow, clock = FakeUnitOfWork(), FakeClock()
    await VerifyEmail(uow, clock)(token)
    assert uow.committed

Like ``common_security.testing``: for tests only, never used by the running service.
"""

import hashlib
from collections.abc import Collection
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Self
from uuid import UUID

from accounts.domain.driver import DriverProfile, DriverStatus
from accounts.domain.email import Email
from accounts.domain.errors import EmailTakenError
from accounts.domain.refresh_token import RefreshToken
from accounts.domain.reputation import Reputation
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

    def __init__(self) -> None:
        self.dummy_checks = 0

    def hash(self, password: str) -> str:
        return "fake$" + hashlib.sha256(password.encode()).hexdigest()

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == self.hash(password)

    def verify_dummy(self, password: str) -> None:
        self.dummy_checks += 1


class FakeAccessTokenIssuer:
    """Readable stand-in tokens: ``access:<user id>:<issued at>``."""

    lifetime = timedelta(minutes=15)

    def issue(self, user: User, now: datetime) -> str:
        return f"access:{user.id}:{now.isoformat()}"


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

    async def get_many(self, user_ids: Collection[UUID]) -> dict[UUID, User]:
        return {i: replace(self.rows[i]) for i in user_ids if i in self.rows}

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


class FakeRefreshTokens:
    def __init__(self) -> None:
        self.rows: dict[UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> None:
        self.rows[token.id] = replace(token)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        found = [token for token in self.rows.values() if token.token_hash == token_hash]
        return replace(found[0]) if found else None

    async def save(self, token: RefreshToken) -> None:
        self.rows[token.id] = replace(token)

    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        for token in self.rows.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now


class FakeDriverProfiles:
    def __init__(self) -> None:
        self.rows: dict[UUID, DriverProfile] = {}

    async def get(self, user_id: UUID, *, for_update: bool = False) -> DriverProfile | None:
        profile = self.rows.get(user_id)
        return replace(profile) if profile else None

    async def save(self, profile: DriverProfile) -> None:
        self.rows[profile.user_id] = replace(profile)

    async def list_by_status(self, status: DriverStatus) -> list[DriverProfile]:
        found = [replace(p) for p in self.rows.values() if p.status is status]
        return sorted(found, key=lambda p: (p.submitted_at is None, p.submitted_at, p.user_id))

    async def get_many(self, user_ids: Collection[UUID]) -> dict[UUID, DriverProfile]:
        return {i: replace(self.rows[i]) for i in user_ids if i in self.rows}


class FakeReputation:
    """Rows only for users a test gives numbers to, like the real table."""

    def __init__(self) -> None:
        self.rows: dict[UUID, Reputation] = {}

    async def get_many(self, user_ids: Collection[UUID]) -> dict[UUID, Reputation]:
        return {i: self.rows[i] for i in user_ids if i in self.rows}


class FakeDocumentStorage:
    """Files in a dict. ``fail_on_save`` makes the next save raise, for testing cleanup."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.fail_on_save = False

    async def save(self, key: str, content: bytes) -> None:
        if self.fail_on_save:
            raise OSError("disk full")
        self.files[key] = content

    async def read(self, key: str) -> bytes | None:
        return self.files.get(key)

    async def delete(self, key: str) -> None:
        self.files.pop(key, None)


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
        self.refresh_tokens = FakeRefreshTokens()
        self.drivers = FakeDriverProfiles()
        self.reputation = FakeReputation()
        self.events = FakeEvents()
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True
