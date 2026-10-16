"""The verification email (#93): what a student gets after signing up or asking for a new
link. The link opens the web app's verify page (/verify?token=…), which calls Accounts."""

from dataclasses import dataclass
from html import escape
from urllib.parse import urlencode

VERIFY_PATH = "/verify"


@dataclass(frozen=True)
class EmailMessage:
    """An email ready to send, as plain text and HTML (inboxes show whichever they can)."""

    to: str
    subject: str
    text: str
    html: str

    def __repr__(self) -> str:
        # The body holds a working verification link; keep it out of logs and error output.
        return f"EmailMessage(to=<hidden>, subject={self.subject!r})"


def verification_link(web_base_url: str, token: str) -> str:
    """``<web_base_url>/verify?token=<token>``. The base URL comes from configuration, so the
    same code links to localhost in development and the live site in production."""
    return f"{web_base_url.rstrip('/')}{VERIFY_PATH}?{urlencode({'token': token})}"


def verification_email(*, to: str, first_name: str, token: str, web_base_url: str) -> EmailMessage:
    link = verification_link(web_base_url, token)
    text = (
        f"Hi {first_name},\n\n"
        "Welcome to GetDrove! Confirm your UofM email to finish setting up your account:\n\n"
        f"{link}\n\n"
        "The link works once and expires in 24 hours. If it has expired, you can ask for a\n"
        "new one on the page it opens.\n\n"
        "If you didn't sign up for GetDrove, you can ignore this email.\n"
    )
    # The name is the student's own input, so it's escaped: it can't add HTML to the email.
    safe_name, safe_link = escape(first_name), escape(link)
    html = (
        f"<p>Hi {safe_name},</p>"
        "<p>Welcome to GetDrove! Confirm your UofM email to finish setting up your account:</p>"
        f'<p><a href="{safe_link}">Verify my email</a></p>'
        "<p>The link works once and expires in 24 hours. If it has expired, you can ask for "
        "a new one on the page it opens.</p>"
        "<p>If you didn't sign up for GetDrove, you can ignore this email.</p>"
    )
    return EmailMessage(to=to, subject="Verify your GetDrove account", text=text, html=html)
