"""The UofM email rule (#3, #4)."""

import pytest

from accounts.domain.email import Email
from accounts.domain.errors import EmailNotUofMError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ada@myumanitoba.ca", "ada@myumanitoba.ca"),
        ("Ada.Lovelace@MyUManitoba.CA", "ada.lovelace@myumanitoba.ca"),
        ("  ada@myumanitoba.ca \n", "ada@myumanitoba.ca"),
    ],
)
def test_uofm_emails_are_accepted_and_lowercased(raw: str, expected: str) -> None:
    assert Email.parse(raw).value == expected


@pytest.mark.parametrize(
    "raw",
    [
        "ada@gmail.com",
        "ada@umanitoba.ca",
        "ada@notmyumanitoba.ca",
        "ada@myumanitoba.ca.evil.com",
        "@myumanitoba.ca",
        "a@b@myumanitoba.ca",
        "myumanitoba.ca",
        "",
    ],
)
def test_other_emails_are_rejected(raw: str) -> None:
    with pytest.raises(EmailNotUofMError):
        Email.parse(raw)


def test_rejection_matches_the_contract() -> None:
    with pytest.raises(EmailNotUofMError) as caught:
        Email.parse("ada@gmail.com")

    error = caught.value
    assert error.status == 422
    assert error.code == "email_not_uofm"
    assert [e.field for e in error.errors] == ["email"]


def test_emails_that_differ_only_in_case_are_equal() -> None:
    assert Email.parse("ADA@myumanitoba.ca") == Email.parse("ada@MYUMANITOBA.CA")


def test_an_email_reads_as_its_address() -> None:
    assert str(Email.parse("Ada@myumanitoba.ca")) == "ada@myumanitoba.ca"
