"""The User entity: emailVerified and roles as the contract defines them."""

from datetime import UTC, datetime

import pytest

from accounts.domain.email import Email
from accounts.domain.errors import EmailTakenError
from accounts.domain.user import User
from common_web import InvalidInputError


def new_user() -> User:
    return User.register(Email.parse("ada@myumanitoba.ca"), "hash", "Ada", "Lovelace")


def test_a_new_user_is_unverified_and_not_an_admin() -> None:
    user = new_user()

    assert user.email_verified is False
    assert user.roles == ["user"]


def test_each_new_user_gets_its_own_id() -> None:
    assert new_user().id != new_user().id


def test_a_verification_date_means_verified() -> None:
    user = new_user()
    user.email_verified_at = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)

    assert user.email_verified is True


def test_admins_are_also_users() -> None:
    user = new_user()
    user.is_admin = True

    assert user.roles == ["user", "admin"]


def test_email_taken_matches_the_contract() -> None:
    assert EmailTakenError.status == 409
    assert EmailTakenError.code == "email_taken"


def test_names_are_trimmed() -> None:
    user = User.register(Email.parse("ada@myumanitoba.ca"), "hash", " Ada ", "Lovelace\t")

    assert (user.first_name, user.last_name) == ("Ada", "Lovelace")


def test_blank_names_are_invalid_input_naming_each_field() -> None:
    with pytest.raises(InvalidInputError) as caught:
        User.register(Email.parse("ada@myumanitoba.ca"), "hash", "  ", "\t")

    assert (caught.value.status, caught.value.code) == (422, "invalid_input")
    assert [e.field for e in caught.value.errors] == ["firstName", "lastName"]
