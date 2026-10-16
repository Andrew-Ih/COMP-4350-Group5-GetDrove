"""The sign-up use case (#4), with in-memory fakes instead of a database."""

from datetime import timedelta

import pytest

from accounts.application.signup import SignUp
from accounts.domain.errors import EmailNotUofMError, EmailTakenError
from accounts.domain.verification import hash_token
from accounts.testing import FIXED_NOW, FakeClock, FakePasswordHasher, FakeUnitOfWork
from common_web import InvalidInputError
from events.catalog import UserRegistered

PASSWORD = "correct horse battery"  # noqa: S105 (a test password)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def sign_up(uow: FakeUnitOfWork) -> SignUp:
    return SignUp(uow, FakePasswordHasher(), FakeClock())


async def test_signing_up_creates_an_unverified_account(
    uow: FakeUnitOfWork, sign_up: SignUp
) -> None:
    user = await sign_up("Ada.Lovelace@MyUManitoba.ca", PASSWORD, "Ada", "Lovelace")

    saved = uow.users.rows[user.id]
    assert saved.email.value == "ada.lovelace@myumanitoba.ca"
    assert (saved.first_name, saved.last_name) == ("Ada", "Lovelace")
    assert saved.email_verified is False
    assert saved.roles == ["user"]
    assert uow.committed


async def test_the_password_is_stored_only_as_a_hash(uow: FakeUnitOfWork, sign_up: SignUp) -> None:
    user = await sign_up("ada@myumanitoba.ca", PASSWORD, "Ada", "Lovelace")

    saved = uow.users.rows[user.id]
    assert PASSWORD not in saved.password_hash
    assert FakePasswordHasher().verify(saved.password_hash, PASSWORD)


async def test_signing_up_sends_one_verification_email_with_a_working_link(
    uow: FakeUnitOfWork, sign_up: SignUp
) -> None:
    user = await sign_up("ada@myumanitoba.ca", PASSWORD, "Ada", "Lovelace")

    [event] = uow.events.published
    assert isinstance(event, UserRegistered)
    assert (event.user_id, event.email, event.first_name) == (
        user.id,
        "ada@myumanitoba.ca",
        "Ada",
    )
    [token] = uow.verification_tokens.rows.values()
    assert token.token_hash == hash_token(event.verification_token)
    assert token.user_id == user.id
    assert token.expires_at == FIXED_NOW + timedelta(hours=24)


async def test_names_are_trimmed(uow: FakeUnitOfWork, sign_up: SignUp) -> None:
    user = await sign_up("ada@myumanitoba.ca", PASSWORD, "  Ada ", " Lovelace  ")

    assert (uow.users.rows[user.id].first_name, uow.users.rows[user.id].last_name) == (
        "Ada",
        "Lovelace",
    )


@pytest.mark.parametrize(
    ("email", "error", "code"),
    [
        ("ada@gmail.com", EmailNotUofMError, "email_not_uofm"),
        ("a b@myumanitoba.ca", InvalidInputError, "invalid_input"),
    ],
)
async def test_a_bad_email_is_refused_and_nothing_is_saved(
    uow: FakeUnitOfWork,
    sign_up: SignUp,
    email: str,
    error: type[InvalidInputError],
    code: str,
) -> None:
    with pytest.raises(error) as caught:
        await sign_up(email, PASSWORD, "Ada", "Lovelace")

    assert caught.value.code == code
    assert uow.users.rows == {}
    assert uow.events.published == []
    assert not uow.committed


@pytest.mark.parametrize(
    ("first", "last", "blank_fields"),
    [
        ("   ", "Lovelace", ["firstName"]),
        ("Ada", "", ["lastName"]),
        (" ", " ", ["firstName", "lastName"]),
    ],
)
async def test_a_blank_name_is_refused_naming_the_field(
    uow: FakeUnitOfWork, sign_up: SignUp, first: str, last: str, blank_fields: list[str]
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        await sign_up("ada@myumanitoba.ca", PASSWORD, first, last)

    assert caught.value.code == "invalid_input"
    assert [e.field for e in caught.value.errors] == blank_fields
    assert uow.users.rows == {}
    assert not uow.committed


@pytest.mark.parametrize("second_email", ["ada@myumanitoba.ca", "ADA@MyUManitoba.ca"])
async def test_a_second_account_with_the_same_email_is_refused(
    uow: FakeUnitOfWork, sign_up: SignUp, second_email: str
) -> None:
    await sign_up("ada@myumanitoba.ca", PASSWORD, "Ada", "Lovelace")
    uow.committed = False

    with pytest.raises(EmailTakenError):
        await sign_up(second_email, PASSWORD, "Ada", "Lovelace")

    assert len(uow.users.rows) == 1
    assert len(uow.events.published) == 1  # only the first sign-up's
    assert not uow.committed
