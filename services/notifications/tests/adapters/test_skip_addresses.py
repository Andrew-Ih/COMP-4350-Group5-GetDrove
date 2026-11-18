"""SkipAddresses (#415): the demo accounts never get an email in production, everyone else
still does, and the logs never hold the address."""

import logging

import pytest

from notifications.adapters.email.skip_addresses import SkipAddresses, skip_addresses
from notifications.domain.verification_email import EmailMessage

DEMO = "getdrove.demo.*@myumanitoba.ca"


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


def email(to: str) -> EmailMessage:
    return EmailMessage(to=to, subject="Your trip leaves soon", text="text", html="<p>html</p>")


async def test_a_demo_account_gets_no_email() -> None:
    real = RecordingSender()
    sender = SkipAddresses(real, [DEMO])

    await sender.send(email("getdrove.demo.maya@myumanitoba.ca"))

    assert real.sent == []


async def test_a_real_student_still_gets_theirs() -> None:
    real = RecordingSender()
    sender = SkipAddresses(real, [DEMO])
    message = email("maya.chen@myumanitoba.ca")

    await sender.send(message)

    assert real.sent == [message]


@pytest.mark.parametrize(
    "address",
    [
        "GetDrove.Demo.Priya@MyUManitoba.ca",  # case doesn't matter in an address
        " getdrove.demo.noah@myumanitoba.ca ",
    ],
)
def test_matching_ignores_case_and_spaces(address: str) -> None:
    assert SkipAddresses(RecordingSender(), [DEMO]).skips(address)


@pytest.mark.parametrize(
    "address",
    [
        "getdrove.demo.maya@gmail.com",  # another domain
        "notgetdrove.demo.maya@myumanitoba.ca",  # the pattern is the whole address
        "getdrove.demomaya@myumanitoba.ca",
    ],
)
def test_only_whole_matches_are_skipped(address: str) -> None:
    assert not SkipAddresses(RecordingSender(), [DEMO]).skips(address)


def test_any_of_several_patterns_matches() -> None:
    sender = SkipAddresses(RecordingSender(), [DEMO, "test.?@myumanitoba.ca"])

    assert sender.skips("test.1@myumanitoba.ca")
    assert sender.skips("getdrove.demo.owen@myumanitoba.ca")
    assert not sender.skips("test.12@myumanitoba.ca")


async def test_a_skipped_email_is_logged_without_the_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = SkipAddresses(RecordingSender(), [DEMO])

    with caplog.at_level(logging.INFO):
        await sender.send(email("getdrove.demo.emma@myumanitoba.ca"))

    assert "Your trip leaves soon" in caplog.text
    assert "emma" not in caplog.text


def test_with_no_patterns_the_real_sender_is_used_as_it_is() -> None:
    real = RecordingSender()

    assert skip_addresses(real, []) is real
    assert skip_addresses(real, ["  "]) is real
    assert isinstance(skip_addresses(real, [DEMO]), SkipAddresses)
