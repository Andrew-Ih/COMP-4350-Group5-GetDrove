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


def register_handlers(consumer: StreamConsumer, send_email: SendVerificationEmail) -> None:
    @consumer.on(UserRegistered)
    async def user_registered(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(UserRegistered)
        await send_email(
            email=data.email,
            first_name=data.first_name,
            verification_token=data.verification_token,
        )

    @consumer.on(VerificationEmailRequested)
    async def verification_email_requested(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(VerificationEmailRequested)
        await send_email(
            email=data.email,
            first_name=data.first_name,
            verification_token=data.verification_token,
        )
