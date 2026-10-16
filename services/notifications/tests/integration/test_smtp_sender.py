"""SmtpEmailSender against a real Mailpit (#93): the email that arrives is the one we built."""

from typing import Any

import httpx

from notifications.adapters.email.smtp_sender import SmtpEmailSender, SmtpSettings
from notifications.domain.verification_email import verification_email

TOKEN = "Xk29aP0Qm7vB-_abc"  # noqa: S105 (a test token)


def received(mailpit: Any) -> list[dict[str, Any]]:
    """Every message Mailpit caught, with its full text and HTML. ``mailpit`` is the
    conftest fixture (host, ports and API address)."""
    listing = httpx.get(f"{mailpit.api}/messages", timeout=5).json()["messages"]
    return [httpx.get(f"{mailpit.api}/message/{m['ID']}", timeout=5).json() for m in listing]


async def test_the_verification_email_arrives_as_built(empty_mailpit: Any) -> None:
    sender = SmtpEmailSender(
        SmtpSettings(
            host=empty_mailpit.smtp_host,
            port=empty_mailpit.smtp_port,
            sender="GetDrove <no-reply@getdrove.local>",
        )
    )
    message = verification_email(
        to="ada@myumanitoba.ca",
        first_name="Ada",
        token=TOKEN,
        web_base_url="http://localhost:3000",
    )

    await sender.send(message)

    [email] = received(empty_mailpit)
    assert [to["Address"] for to in email["To"]] == ["ada@myumanitoba.ca"]
    assert email["From"]["Address"] == "no-reply@getdrove.local"
    assert email["Subject"] == "Verify your GetDrove account"
    link = f"http://localhost:3000/verify?token={TOKEN}"
    assert link in email["Text"]
    assert f'href="{link}"' in email["HTML"]
