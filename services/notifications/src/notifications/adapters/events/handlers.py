"""Handlers for the events Notifications consumes from Accounts (#93).

Both events ask for the same verification email. ``StreamConsumer`` runs each handler in
the transaction that records the event in ``processed_events``, so a repeat delivery (or a
restart) is skipped instead of sending a second email. A failed send raises, which rolls
that record back, and the event is retried (then parked after 5 tries).

One rare case remains: if the service dies after the mail server accepted the email but
before that transaction commits, the email is sent again on restart. libs/events
documents this; a second copy of the same link is harmless.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import UserRegistered, VerificationEmailRequested
from events.consumer import StreamConsumer
from notifications.application.send_verification_email import SendVerificationEmail

# The events that ask for a verification email. Both have the same fields.
VERIFICATION_EMAIL_EVENTS: dict[str, type[UserRegistered] | type[VerificationEmailRequested]] = {
    UserRegistered.event_type: UserRegistered,
    VerificationEmailRequested.event_type: VerificationEmailRequested,
}


def register_handlers(consumer: StreamConsumer, send_email: SendVerificationEmail) -> None:
    async def send_verification_email(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(VERIFICATION_EMAIL_EVENTS[event.type])
        await send_email(
            email=data.email,
            first_name=data.first_name,
            verification_token=data.verification_token,
        )

    for payload in VERIFICATION_EMAIL_EVENTS.values():
        consumer.on(payload)(send_verification_email)
