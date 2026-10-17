"""The refresh and logout use cases (#90), with in-memory fakes instead of a database."""

from datetime import timedelta

import pytest

from accounts.application.session import LogOut, RefreshSession
from accounts.domain.email import Email
from accounts.domain.errors import InvalidRefreshTokenError
from accounts.domain.refresh_token import RefreshToken
from accounts.domain.user import User
from accounts.domain.verification import hash_token
from accounts.testing import FIXED_NOW, FakeAccessTokenIssuer, FakeClock, FakeUnitOfWork


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def refresh(uow: FakeUnitOfWork, clock: FakeClock) -> RefreshSession:
    return RefreshSession(uow, FakeAccessTokenIssuer(), clock)


async def logged_in(uow: FakeUnitOfWork, email: str = "ada@myumanitoba.ca") -> tuple[User, str]:
    """A verified student with one session; returns them and their cookie."""
    user = User.register(Email.parse(email), "hash", "Ada", "Lovelace")
    user.email_verified_at = FIXED_NOW
    await uow.users.add(user)
    token, cookie = RefreshToken.issue(user.id, FIXED_NOW)
    await uow.refresh_tokens.add(token)
    return user, cookie


def active_sessions(uow: FakeUnitOfWork, user: User) -> int:
    return sum(
        1
        for t in uow.refresh_tokens.rows.values()
        if t.user_id == user.id and t.is_active(FIXED_NOW)
    )


# ---------------------------------------------------------------- refresh


async def test_refreshing_swaps_the_cookie_and_issues_an_access_token(
    uow: FakeUnitOfWork, clock: FakeClock, refresh: RefreshSession
) -> None:
    user, cookie = await logged_in(uow)
    clock.current = FIXED_NOW + timedelta(minutes=20)

    result = await refresh(cookie)

    assert result.access_token == f"access:{user.id}:{clock.current.isoformat()}"
    assert result.expires_in == 900
    assert result.refresh_token != cookie
    old = await uow.refresh_tokens.get_by_hash(hash_token(cookie))
    new = await uow.refresh_tokens.get_by_hash(hash_token(result.refresh_token))
    assert old is not None and new is not None
    assert old.revoked_at == clock.current
    assert old.replaced_by_id == new.id
    assert new.expires_at == clock.current + timedelta(days=7)
    assert uow.committed


async def test_the_new_cookie_keeps_working(uow: FakeUnitOfWork, refresh: RefreshSession) -> None:
    _, cookie = await logged_in(uow)

    second = await refresh((await refresh(cookie)).refresh_token)

    assert second.refresh_token


@pytest.mark.parametrize("cookie", [None, "", "not-a-real-token"])
async def test_a_missing_or_unknown_cookie_is_401(
    uow: FakeUnitOfWork, refresh: RefreshSession, cookie: str | None
) -> None:
    with pytest.raises(InvalidRefreshTokenError):
        await refresh(cookie)

    assert not uow.committed


async def test_an_expired_cookie_is_401(
    uow: FakeUnitOfWork, clock: FakeClock, refresh: RefreshSession
) -> None:
    _, cookie = await logged_in(uow)
    clock.current = FIXED_NOW + timedelta(days=7)

    with pytest.raises(InvalidRefreshTokenError):
        await refresh(cookie)

    assert not uow.committed


async def test_reusing_a_swapped_cookie_ends_all_of_that_students_sessions(
    uow: FakeUnitOfWork, refresh: RefreshSession
) -> None:
    user, stolen = await logged_in(uow)
    await refresh(stolen)  # the real student refreshes: `stolen` is now swapped
    other, _ = await logged_in(uow, "grace@myumanitoba.ca")
    uow.committed = False

    with pytest.raises(InvalidRefreshTokenError):
        await refresh(stolen)  # someone presents the old copy

    assert active_sessions(uow, user) == 0  # including the student's newest cookie
    assert active_sessions(uow, other) == 1  # nobody else is affected
    assert uow.committed  # the lockout is saved even though the request is refused


async def test_a_logged_out_cookie_is_401_without_ending_other_sessions(
    uow: FakeUnitOfWork, clock: FakeClock, refresh: RefreshSession
) -> None:
    user, laptop = await logged_in(uow)
    phone_token, _ = RefreshToken.issue(user.id, FIXED_NOW)
    await uow.refresh_tokens.add(phone_token)
    await LogOut(uow, clock)(laptop)

    with pytest.raises(InvalidRefreshTokenError):
        await refresh(laptop)

    assert active_sessions(uow, user) == 1  # the phone is still logged in


async def test_a_cookie_for_a_deleted_account_is_401(
    uow: FakeUnitOfWork, refresh: RefreshSession
) -> None:
    user, cookie = await logged_in(uow)
    del uow.users.rows[user.id]

    with pytest.raises(InvalidRefreshTokenError):
        await refresh(cookie)

    assert not uow.committed


# ---------------------------------------------------------------- logout


async def test_logging_out_stops_the_cookie_working(
    uow: FakeUnitOfWork, clock: FakeClock, refresh: RefreshSession
) -> None:
    user, cookie = await logged_in(uow)

    await LogOut(uow, clock)(cookie)

    assert active_sessions(uow, user) == 0
    assert uow.committed
    with pytest.raises(InvalidRefreshTokenError):
        await refresh(cookie)


@pytest.mark.parametrize("cookie", [None, "", "not-a-real-token"])
async def test_logging_out_without_a_session_still_succeeds(
    uow: FakeUnitOfWork, clock: FakeClock, cookie: str | None
) -> None:
    await LogOut(uow, clock)(cookie)

    assert not uow.committed


async def test_logging_out_twice_still_succeeds(uow: FakeUnitOfWork, clock: FakeClock) -> None:
    _, cookie = await logged_in(uow)
    await LogOut(uow, clock)(cookie)
    uow.committed = False

    await LogOut(uow, clock)(cookie)

    assert not uow.committed  # nothing left to change
