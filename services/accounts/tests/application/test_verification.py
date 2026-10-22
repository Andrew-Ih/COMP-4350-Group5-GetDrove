"""The email verification use cases (#5), with in-memory fakes instead of a database."""

from datetime import timedelta

import pytest

from accounts.application.verification import (
    ResendVerification,
    VerifyEmail,
    issue_verification_token,
)
from accounts.domain.email import Email
from accounts.domain.errors import InvalidVerificationTokenError, VerificationTokenExpiredError
from accounts.domain.user import User
from accounts.domain.verification import hash_token
from accounts.testing import FIXED_NOW as NOW
from accounts.testing import FakeClock, FakeUnitOfWork
from events.catalog import VerificationEmailRequested


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
