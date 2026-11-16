"""The email that goes with a notification (#146)."""

from uuid import uuid4

from notifications.domain.messages import Message
from notifications.domain.notification_email import Contact, notification_email
from notifications.domain.notifications import NotificationType

ADA = Contact(first_name="Ada", email="ada@myumanitoba.ca")


def message(body: str = "You have a seat on the trip.") -> Message:
    return Message(
        user_id=uuid4(),
        type=NotificationType.REQUEST_ACCEPTED,
        title="Request accepted",
        body=body,
        link_path="/trips",
    )


def test_the_email_greets_them_says_what_happened_and_links_to_the_app() -> None:
    email = notification_email(ADA, message(), "https://getdrove.example/")

    assert email.to == "ada@myumanitoba.ca"
    assert email.subject == "Request accepted"
    assert email.text.startswith("Hi Ada,")
    assert "You have a seat on the trip." in email.text
    assert "https://getdrove.example/trips" in email.text
    assert 'href="https://getdrove.example/trips"' in email.html


def test_other_peoples_text_cant_add_html() -> None:
    contact = Contact(first_name="<b>Ada</b>", email="ada@myumanitoba.ca")

    email = notification_email(contact, message("Pickup: <script>x</script>."), "https://x")

    assert "<script>" not in email.html
    assert "<b>Ada</b>" not in email.html
    assert "&lt;script&gt;" in email.html


def test_a_contact_never_shows_its_email_when_printed() -> None:
    assert "ada@" not in repr(ADA)
