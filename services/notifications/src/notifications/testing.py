"""In-memory fakes of Notifications' ports, for tests only (like ``accounts.testing``)."""

from notifications.domain.verification_email import EmailMessage


class FakeEmailSender:
    """Keeps sent emails in ``sent``. Set ``fail_with`` to make the next sends raise."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    async def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)
