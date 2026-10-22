"""The verification email (#93)."""

from urllib.parse import parse_qs, urlparse

import pytest

from notifications.domain.verification_email import (
    EmailMessage,
    verification_email,
    verification_link,
)

TOKEN = "Xk29aP0Qm7vB-_abc"  # noqa: S105 (a test token)


def email(**overrides: str) -> EmailMessage:
    values = {
        "to": "ada@myumanitoba.ca",
        "first_name": "Ada",
        "token": TOKEN,
        "web_base_url": "http://localhost:3000",
        **overrides,
    }
    return verification_email(**values)


@pytest.mark.parametrize("base", ["http://localhost:3000", "http://localhost:3000/"])
def test_the_link_opens_the_verify_page_with_the_token(base: str) -> None:
    link = verification_link(base, TOKEN)

    assert link == f"http://localhost:3000/verify?token={TOKEN}"
    assert parse_qs(urlparse(link).query) == {"token": [TOKEN]}


def test_the_link_uses_the_configured_site() -> None:
    link = verification_link("https://getdrove.example", TOKEN)

    assert link.startswith("https://getdrove.example/verify?token=")


def test_the_email_greets_the_student_and_carries_the_link() -> None:
    message = email()

    assert message.to == "ada@myumanitoba.ca"
    assert message.subject == "Verify your GetDrove account"
    link = f"http://localhost:3000/verify?token={TOKEN}"
    assert "Hi Ada," in message.text
    assert link in message.text
    assert f'href="{link}"' in message.html
    assert "24 hours" in message.text
    assert "24 hours" in message.html


def test_a_name_cant_add_html_to_the_email() -> None:
    message = email(first_name='<a href="https://evil.example">Ada</a>')

    assert '<a href="https://evil.example">' not in message.html
    assert "&lt;a href=&quot;https://evil.example&quot;&gt;" in message.html


def test_the_link_never_shows_up_in_logs() -> None:
    message = email()

    assert TOKEN not in repr(message)
    assert "ada@myumanitoba.ca" not in repr(message)
