"""The login and /me use cases (#6), with in-memory fakes instead of a database."""

from datetime import timedelta
from uuid import uuid4

import pytest

from accounts.application.login import GetMe, LogIn
from accounts.domain.email import Email
from accounts.domain.errors import EmailNotVerifiedError, InvalidCredentialsError
from accounts.domain.user import User
from accounts.domain.verification import hash_token
from accounts.testing import (
    FIXED_NOW,
    FakeAccessTokenIssuer,
    FakeClock,
    FakePasswordHasher,
    FakeUnitOfWork,
)
from common_web import UnauthorizedError

PASSWORD = "correct horse battery"  # noqa: S105 (a test password)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def log_in(uow: FakeUnitOfWork, hasher: FakePasswordHasher) -> LogIn:
    return LogIn(uow, hasher, FakeAccessTokenIssuer(), FakeClock())


async def account(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, *, verified: bool = True
) -> User:
    user = User.register(
        Email.parse("ada@myumanitoba.ca"), hasher.hash(PASSWORD), "Ada", "Lovelace"
    )
    user.email_verified_at = FIXED_NOW if verified else None
    await uow.users.add(user)
    return user


# ---------------------------------------------------------------- success


async def test_logging_in_returns_an_access_token_and_a_refresh_token(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn
) -> None:
    user = await account(uow, hasher)

    result = await log_in("ada@myumanitoba.ca", PASSWORD)

    assert result.access_token == f"access:{user.id}:{FIXED_NOW.isoformat()}"
    assert result.expires_in == 900
    [saved] = uow.refresh_tokens.rows.values()
    assert saved.user_id == user.id
    assert saved.token_hash == hash_token(result.refresh_token)  # only the hash is stored
    assert saved.expires_at == FIXED_NOW + timedelta(days=7)
    assert uow.committed


async def test_the_email_isnt_case_sensitive(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn
) -> None:
    await account(uow, hasher)

    await log_in("  ADA@MyUManitoba.ca ", PASSWORD)

    assert uow.committed


# ---------------------------------------------------------------- refused


@pytest.mark.parametrize(
    "email",
    [
        "nobody@myumanitoba.ca",  # no account
        "ada@gmail.com",  # can't have an account
        "a b@myumanitoba.ca",  # a typo
    ],
)
async def test_an_unknown_email_is_401_after_a_dummy_password_check(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn, email: str
) -> None:
    await account(uow, hasher)

    with pytest.raises(InvalidCredentialsError) as caught:
        await log_in(email, PASSWORD)

    assert caught.value.detail == "Wrong email or password."
    assert hasher.dummy_checks == 1  # same work as a real check, so the same timing
    assert uow.refresh_tokens.rows == {}
    assert not uow.committed


async def test_a_wrong_password_is_the_same_401(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn
) -> None:
    await account(uow, hasher)

    with pytest.raises(InvalidCredentialsError) as caught:
        await log_in("ada@myumanitoba.ca", "wrong password")

    assert caught.value.detail == "Wrong email or password."
    assert uow.refresh_tokens.rows == {}
    assert not uow.committed


async def test_an_unverified_account_with_the_right_password_is_403(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn
) -> None:
    await account(uow, hasher, verified=False)

    with pytest.raises(EmailNotVerifiedError):
        await log_in("ada@myumanitoba.ca", PASSWORD)

    assert uow.refresh_tokens.rows == {}
    assert not uow.committed


async def test_an_unverified_account_with_a_wrong_password_is_401_not_403(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, log_in: LogIn
) -> None:
    """Otherwise anyone could learn an account exists by guessing any password."""
    await account(uow, hasher, verified=False)

    with pytest.raises(InvalidCredentialsError):
        await log_in("ada@myumanitoba.ca", "wrong password")


# ---------------------------------------------------------------- /me


async def test_me_returns_the_logged_in_user(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher
) -> None:
    user = await account(uow, hasher)

    assert await GetMe(uow)(user.id) == user


async def test_me_is_401_if_the_account_no_longer_exists(uow: FakeUnitOfWork) -> None:
    with pytest.raises(UnauthorizedError):
        await GetMe(uow)(uuid4())
