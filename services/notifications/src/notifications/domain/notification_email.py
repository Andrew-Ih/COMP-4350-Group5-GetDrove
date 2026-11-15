"""The email that goes with an in-app notification (#146): short and plain, with one link
into the web app."""

from dataclasses import dataclass
from html import escape

from notifications.domain.messages import Message
from notifications.domain.verification_email import EmailMessage


@dataclass(frozen=True)
class Contact:
    """Where to email someone, from Accounts. Never logged or stored here."""

    first_name: str
    email: str

    def __repr__(self) -> str:
        return "Contact(<hidden>)"


def notification_email(contact: Contact, message: Message, web_base_url: str) -> EmailMessage:
    link = f"{web_base_url.rstrip('/')}{message.link_path}"
    text = (
        f"Hi {contact.first_name},\n\n"
        f"{message.body}\n\n"
        f"Open GetDrove: {link}\n\n"
        "You're getting this because you use GetDrove.\n"
    )
    # Names, pickup labels and rejection reasons are other people's input: escape them all.
    html = (
        f"<p>Hi {escape(contact.first_name)},</p>"
        f"<p>{escape(message.body)}</p>"
        f'<p><a href="{escape(link)}">Open GetDrove</a></p>'
        "<p>You're getting this because you use GetDrove.</p>"
    )
    return EmailMessage(to=contact.email, subject=message.title, text=text, html=html)
