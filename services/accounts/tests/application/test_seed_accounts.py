"""The SeedAccounts use case (#111), with in-memory fakes instead of a database."""

import pytest

from accounts.application.seed_accounts import DemoAccount, SeedAccounts
from accounts.domain.email import Email
from accounts.domain.errors import EmailNotUofMError
from accounts.domain.user import User
from accounts.testing import FIXED_NOW, FakeClock, FakePasswordHasher, FakeUnitOfWork
from common_web import InvalidInputError

PASSWORD = "demo password 2026"  # noqa: S105 (a test password)
MAYA = DemoAccount("getdrove.demo.maya@myumanitoba.ca", "Maya", "Chen")
PRIYA = DemoAccount("getdrove.demo.priya@myumanitoba.ca", "Priya", "Sharma")


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def seed(uow: FakeUnitOfWork) -> SeedAccounts:
    return SeedAccounts(uow, FakePasswordHasher(), FakeClock())


async def test_it_creates_verified_accounts_that_can_log_in(
    uow: FakeUnitOfWork, seed: SeedAccounts
) -> None:
    result = await seed([MAYA, PRIYA], PASSWORD)

    assert result.created == [MAYA.email, PRIYA.email]
    assert result.already_there == []
    assert uow.committed
    users = list(uow.users.rows.values())
    assert {u.email.value for u in users} == {MAYA.email, PRIYA.email}
    for user in users:
        assert user.email_verified_at == FIXED_NOW  # no email to click
        assert user.roles == ["user"]
        assert PASSWORD not in user.password_hash
        assert FakePasswordHasher().verify(user.password_hash, PASSWORD)


async def test_it_sends_no_verification_email(uow: FakeUnitOfWork, seed: SeedAccounts) -> None:
    await seed([MAYA], PASSWORD)

    assert uow.events.published == []
    assert uow.verification_tokens.rows == {}


async def test_running_it_again_leaves_existing_accounts_alone(
    uow: FakeUnitOfWork, seed: SeedAccounts
) -> None:
    existing = User.register(Email.parse(MAYA.email), "their own hash", "Maya", "Chen")
    await uow.users.add(existing)

    result = await seed([MAYA, PRIYA], PASSWORD)

    assert result.created == [PRIYA.email]
    assert result.already_there == [MAYA.email]
    untouched = "their own hash"
    assert uow.users.rows[existing.id].password_hash == untouched


async def test_a_short_password_is_refused_before_anything_is_saved(
    uow: FakeUnitOfWork, seed: SeedAccounts
) -> None:
    with pytest.raises(InvalidInputError):
        await seed([MAYA], "short")

    assert uow.users.rows == {}
    assert not uow.committed


async def test_one_bad_email_stops_the_whole_seed(uow: FakeUnitOfWork, seed: SeedAccounts) -> None:
    with pytest.raises(EmailNotUofMError):
        await seed([MAYA, DemoAccount("someone@gmail.com", "Some", "One")], PASSWORD)

    assert uow.users.rows == {}
    assert not uow.committed
