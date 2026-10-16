"""SmtpEmailSender's production path (#93): Brevo needs STARTTLS, then a login, before
sending. Mailpit uses neither, so this checks the order against a stand-in for smtplib."""

from typing import Any, ClassVar, Self

import pytest

from notifications.adapters.email import smtp_sender
from notifications.adapters.email.smtp_sender import SmtpEmailSender, SmtpSettings
from notifications.domain.verification_email import verification_email


class RecordingSmtp:
    """Records what the sender does with the connection, in order."""

    calls: ClassVar[list[str]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.calls.append(f"connect {host}:{port}")

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.calls.append("quit")

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append(f"login {username}")

    def send_message(self, message: Any) -> None:
        self.calls.append(f"send to {message['To']}")


@pytest.fixture(autouse=True)
def recording_smtp(monkeypatch: pytest.MonkeyPatch) -> type[RecordingSmtp]:
    RecordingSmtp.calls = []
    monkeypatch.setattr(smtp_sender.smtplib, "SMTP", RecordingSmtp)
    return RecordingSmtp


MESSAGE = verification_email(
    to="ada@myumanitoba.ca",
    first_name="Ada",
    token="t",  # noqa: S106 (a test value)
    web_base_url="https://x",
)


async def test_production_encrypts_and_logs_in_before_sending() -> None:
    sender = SmtpEmailSender(
        SmtpSettings(
            host="smtp-relay.brevo.com",
            port=587,
            sender="GetDrove <no-reply@getdrove.app>",
            username="brevo-user",
            password="brevo-key",  # noqa: S106 (a test value)
            starttls=True,
        )
    )

    await sender.send(MESSAGE)

    assert RecordingSmtp.calls == [
        "connect smtp-relay.brevo.com:587",
        "starttls",
        "login brevo-user",
        "send to ada@myumanitoba.ca",
        "quit",
    ]


async def test_locally_it_just_sends() -> None:
    sender = SmtpEmailSender(SmtpSettings(host="localhost", port=1025, sender="x@y.z"))

    await sender.send(MESSAGE)

    assert RecordingSmtp.calls == ["connect localhost:1025", "send to ada@myumanitoba.ca", "quit"]
