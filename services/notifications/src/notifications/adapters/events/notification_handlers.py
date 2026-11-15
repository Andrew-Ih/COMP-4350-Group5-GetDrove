"""Handlers that turn request, trip, driver and payment events into notifications (#146).

| Event | Stream | Who is told |
|---|---|---|
| ``SeatRequested`` | trips | the driver |
| ``RequestAccepted`` | trips | the rider; the driver too if it was auto-accepted |
| ``RequestDeclined`` | trips | the rider |
| ``RequestCancelled`` | trips | the driver |
| ``TripCancelled`` | trips | every rider with a pending or accepted request |
| ``DriverApproved`` / ``DriverRejected`` | accounts | the driver |
| ``PaymentFailed`` | payments | the rider |

Each one is an in-app notification and an email. ``StreamConsumer`` runs each handler in
the transaction that records the event in ``processed_events``, so a repeated event
notifies nobody twice; a failure rolls everything back and the event is retried.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import (
    DriverApproved,
    DriverRejected,
    PaymentFailed,
    RequestAccepted,
    RequestCancelled,
    RequestDeclined,
    SeatRequested,
    TripCancelled,
)
from events.consumer import StreamConsumer
from notifications.adapters.events.registration import HandlerMap, register_event_handlers
from notifications.adapters.persistence.notification_store import SQLAlchemyNotificationStore
from notifications.adapters.persistence.trip_members import SQLAlchemyTripMembers
from notifications.application.notify import Notify
from notifications.application.ports import ContactDirectory, EmailSender
from notifications.application.trip_events import TripEventNotifications


def notification_handlers(
    *,
    contacts: ContactDirectory,
    sender: EmailSender,
    web_base_url: str,
) -> HandlerMap:
    """The notification handlers, by event."""

    def use_case(session: AsyncSession) -> TripEventNotifications:
        """Everything for one event works in its session, so it commits (or rolls back)
        together with the event's processed_events row."""
        notify = Notify(
            store=SQLAlchemyNotificationStore(session),
            contacts=contacts,
            sender=sender,
            web_base_url=web_base_url,
        )
        return TripEventNotifications(notify, SQLAlchemyTripMembers(session))

    async def on_seat_requested(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(SeatRequested)
        await use_case(session).seat_requested(
            request_id=data.request_id,
            trip_id=data.trip_id,
            driver_id=data.driver_id,
            departure_at=data.departure_at,
        )

    async def on_request_accepted(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(RequestAccepted)
        await use_case(session).request_accepted(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            driver_id=data.driver_id,
            departure_at=data.departure_at,
            pickup_label=data.pickup_label,
            auto_accepted=data.auto_accepted,
        )

    async def on_request_declined(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(RequestDeclined)
        await use_case(session).request_declined(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            was_accepted=data.was_accepted,
        )

    async def on_request_cancelled(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(RequestCancelled)
        await use_case(session).request_cancelled(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            driver_id=data.driver_id,
            was_accepted=data.was_accepted,
        )

    async def on_trip_cancelled(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(TripCancelled)
        await use_case(session).trip_cancelled(
            trip_id=data.trip_id, rider_ids=data.rider_ids, departure_at=data.departure_at
        )

    async def on_driver_approved(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(DriverApproved)
        await use_case(session).driver_approved(driver_id=data.user_id)

    async def on_driver_rejected(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(DriverRejected)
        await use_case(session).driver_rejected(driver_id=data.user_id, reason=data.reason)

    async def on_payment_failed(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(PaymentFailed)
        await use_case(session).payment_failed(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            reason=data.reason,
        )

    return {
        SeatRequested: on_seat_requested,
        RequestAccepted: on_request_accepted,
        RequestDeclined: on_request_declined,
        RequestCancelled: on_request_cancelled,
        TripCancelled: on_trip_cancelled,
        DriverApproved: on_driver_approved,
        DriverRejected: on_driver_rejected,
        PaymentFailed: on_payment_failed,
    }


def register_notification_handlers(
    consumer: StreamConsumer,
    *,
    contacts: ContactDirectory,
    sender: EmailSender,
    web_base_url: str,
) -> None:
    """Only the notifications, on a consumer of their own (tests). The service registers them
    together with the reminders (``registration.register_event_handlers``)."""
    register_event_handlers(
        consumer,
        notification_handlers(contacts=contacts, sender=sender, web_base_url=web_base_url),
    )
