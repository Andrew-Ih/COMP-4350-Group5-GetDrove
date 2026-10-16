"""The real ``EmailSender``: SMTP, with Python's built-in smtplib (ADR 0010).

Locally it talks to Mailpit (no login, no TLS), which catches every email so nothing
reaches a real inbox. In production it talks to Brevo's SMTP relay, with STARTTLS and a
login from the server's secrets.
"""

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage

from notifications.domain.verification_email import EmailMessage


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    sender: str  # the From address, e.g. "GetDrove <no-reply@...>"
    username: str | None = None
    password: str | None = None
    starttls: bool = False
    timeout_seconds: float = 10.0


class SmtpEmailSender:
    def __init__(self, settings: SmtpSettings) -> None:
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        # smtplib blocks while it talks to the server, so it runs in a worker thread and
        # doesn't hold up the rest of the service.
        await asyncio.to_thread(self._send, _to_mime(message, self._settings.sender))

    def _send(self, mime: MimeMessage) -> None:
        settings = self._settings
        with smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout_seconds) as smtp:
            if settings.starttls:
                smtp.starttls()
            if settings.username and settings.password:
                smtp.login(settings.username, settings.password)
            smtp.send_message(mime)


def _to_mime(message: EmailMessage, sender: str) -> MimeMessage:
    mime = MimeMessage()
    mime["From"] = sender
    mime["To"] = message.to  # a newline here raises, so headers can't be injected
    mime["Subject"] = message.subject
    mime.set_content(message.text)
    mime.add_alternative(message.html, subtype="html")
    return mime
