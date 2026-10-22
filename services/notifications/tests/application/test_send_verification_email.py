"""The SendVerificationEmail use case (#93), with a fake sender."""

import pytest

from notifications.application.send_verification_email import SendVerificationEmail
from notifications.testing import FakeEmailSender

TOKEN = "Xk29aP0Qm7vB-_abc"  # noqa: S105 (a test token)


async def test_the_student_gets_one_email_linking_to_the_configured_site() -> None:
    sender = FakeEmailSender()

    await SendVerificationEmail(sender, "https://getdrove.example")(
        email="ada@myumanitoba.ca", first_name="Ada", verification_token=TOKEN
    )

    [message] = sender.sent
    assert message.to == "ada@myumanitoba.ca"
    assert "Hi Ada," in message.text
    assert f"https://getdrove.example/verify?token={TOKEN}" in message.text


async def test_a_failed_send_raises_so_the_event_is_retried() -> None:
    sender = FakeEmailSender()
    sender.fail_with = ConnectionError("mail server down")

    with pytest.raises(ConnectionError):
        await SendVerificationEmail(sender, "http://localhost:3000")(
            email="ada@myumanitoba.ca", first_name="Ada", verification_token=TOKEN
        )
