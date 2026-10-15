"""The email verification use cases (#5), with in-memory fakes instead of a database."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Self
from uuid import UUID

import pytest

from accounts.application.verification import (
    ResendVerification,
    VerifyEmail,
    issue_verification_token,
)
from accounts.domain.email import Email
from accounts.domain.errors import InvalidVerificationTokenError, VerificationTokenExpiredError
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken, hash_token
from events import EventPayload
from events.catalog import VerificationEmailRequested

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


# ---------------------------------------------------------------- fakes


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class FakeUsers:
    """Stores copies, like a database: changing a User does nothing until ``save``."""

    def __init__(self) -> None:
        self.rows: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        self.rows[user.id] = replace(user)

    async def get(self, user_id: UUID) -> User | None:
        user = self.rows.get(user_id)
        return replace(user) if user else None

    async def get_by_email(self, email: Email) -> User | None:
        found = [u for u in self.rows.values() if u.email == email]
        return replace(found[0]) if found else None

    async def save(self, user: User) -> None:
        self.rows[user.id] = replace(user)


class FakeTokens:
    def __init__(self) -> None:
        self.rows: dict[UUID, VerificationToken] = {}

    async def add(self, token: VerificationToken) -> None:
        self.rows[token.id] = replace(token)

    async def get_by_hash(self, token_hash: str) -> VerificationToken | None:
        found = [t for t in self.rows.values() if t.token_hash == token_hash]
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
    def __init__(self) -> None:
        self.users = FakeUsers()
        self.verification_tokens = FakeTokens()
        self.events = FakeEvents()
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


# ---------------------------------------------------------------- helpers


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


async def unverified_user(uow: FakeUnitOfWork, email: str = "ada@myumanitoba.ca") -> User:
    user = User.register(Email.parse(email), "argon2-hash", "Ada", "Lovelace")
    await uow.users.add(user)
    return user


async def link_for(uow: FakeUnitOfWork, user: User, clock: FakeClock) -> str:
    """A token for the user's verification link, already saved."""
    return await issue_verification_token(uow, user, clock)


# ---------------------------------------------------------------- issuing


async def test_an_issued_token_is_saved_as_a_hash_only(
    uow: FakeUnitOfWork, clock: FakeClock
) -> None:
    user = await unverified_user(uow)

    link_token = await issue_verification_token(uow, user, clock)

    [saved] = uow.verification_tokens.rows.values()
    assert saved.token_hash == hash_token(link_token)
    assert saved.user_id == user.id
    assert saved.expires_at == NOW + timedelta(hours=24)


# ---------------------------------------------------------------- verify


async def test_a_valid_link_verifies_the_email(uow: FakeUnitOfWork, clock: FakeClock) -> None:
    user = await unverified_user(uow)
    link_token = await link_for(uow, user, clock)
    clock.current = NOW + timedelta(hours=2)

    await VerifyEmail(uow, clock)(link_token)

    assert uow.users.rows[user.id].email_verified_at == NOW + timedelta(hours=2)
    [token] = uow.verification_tokens.rows.values()
    assert token.consumed_at == NOW + timedelta(hours=2)
    assert uow.committed


async def test_a_second_valid_link_keeps_the_first_verification_time(
    uow: FakeUnitOfWork, clock: FakeClock
) -> None:
    user = await unverified_user(uow)
    first_link = await link_for(uow, user, clock)
    second_link = await link_for(uow, user, clock)
    await VerifyEmail(uow, clock)(first_link)
    clock.current = NOW + timedelta(hours=3)

    await VerifyEmail(uow, clock)(second_link)

    assert uow.users.rows[user.id].email_verified_at == NOW


async def test_an_unknown_link_is_invalid(uow: FakeUnitOfWork, clock: FakeClock) -> None:
    with pytest.raises(InvalidVerificationTokenError):
        await VerifyEmail(uow, clock)("not-a-real-token")

    assert not uow.committed


async def test_a_link_works_only_once(uow: FakeUnitOfWork, clock: FakeClock) -> None:
    user = await unverified_user(uow)
    link_token = await link_for(uow, user, clock)
    await VerifyEmail(uow, clock)(link_token)
    uow.committed = False

    with pytest.raises(InvalidVerificationTokenError):
        await VerifyEmail(uow, clock)(link_token)
    assert not uow.committed


async def test_an_expired_link_is_refused(uow: FakeUnitOfWork, clock: FakeClock) -> None:
    user = await unverified_user(uow)
    link_token = await link_for(uow, user, clock)
    clock.current = NOW + timedelta(hours=24)

    with pytest.raises(VerificationTokenExpiredError):
        await VerifyEmail(uow, clock)(link_token)

    assert uow.users.rows[user.id].email_verified is False
    assert not uow.committed


# ---------------------------------------------------------------- resend


@pytest.mark.parametrize(
    "email",
    [
        "nobody@myumanitoba.ca",  # no account
        "ada@gmail.com",  # not a UofM email
        "a b@myumanitoba.ca",  # a typo
    ],
)
async def test_resend_quietly_does_nothing_for_emails_without_an_unverified_account(
    uow: FakeUnitOfWork, clock: FakeClock, email: str
) -> None:
    await unverified_user(uow)

    await ResendVerification(uow, clock)(email)

    assert uow.events.published == []
    assert uow.verification_tokens.rows == {}
    assert not uow.committed


async def test_resend_quietly_does_nothing_for_a_verified_account(
    uow: FakeUnitOfWork, clock: FakeClock
) -> None:
    user = await unverified_user(uow)
    user.email_verified_at = NOW
    await uow.users.save(user)

    await ResendVerification(uow, clock)("ada@myumanitoba.ca")

    assert uow.events.published == []
    assert not uow.committed


async def test_resend_replaces_the_old_link_and_asks_for_an_email(
    uow: FakeUnitOfWork, clock: FakeClock
) -> None:
    user = await unverified_user(uow)
    old_link = await link_for(uow, user, clock)
    clock.current = NOW + timedelta(hours=1)

    await ResendVerification(uow, clock)("Ada@MyUManitoba.ca")

    assert uow.committed
    [event] = uow.events.published
    assert isinstance(event, VerificationEmailRequested)
    assert (event.user_id, event.email, event.first_name) == (
        user.id,
        "ada@myumanitoba.ca",
        "Ada",
    )

    # The old link no longer works; the emailed one does.
    with pytest.raises(InvalidVerificationTokenError):
        await VerifyEmail(uow, clock)(old_link)
    await VerifyEmail(uow, clock)(event.verification_token)
    assert uow.users.rows[user.id].email_verified
