"""Handlers that keep trip reminders in step with Trips' events (#148).

- ``RequestAccepted``: schedule the rider's reminder, 30 minutes (configurable) before
  departure.
- ``RequestCancelled``: the rider cancelled, so cancel their reminder.
- ``RequestDeclined`` of a rider who had a seat: the driver removed them, so cancel it.
- ``TripCancelled``: cancel every reminder on the trip.

``StreamConsumer`` runs each handler in the transaction that records the event in
``processed_events``, so a repeated event is skipped. The unique ``request_id`` is a second
guard: even a ``RequestAccepted`` republished under a new event ID adds no second reminder.

Events on one stream arrive in order. The exception is a handler that fails and is retried
later (after 30 s): if a cancellation is handled in the meantime, it finds no reminder to
cancel, and the retried ``RequestAccepted`` then schedules one. That needs a database
failure on the first event, and #149 can check the trip before sending if it proves to
matter.
"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from notifications.adapters.events.registration import HandlerMap, register_event_handlers
from notifications.adapters.persistence.reminder_store import SQLAlchemyReminderStore
from notifications.application.trip_reminders import CancelTripReminders, ScheduleTripReminder


async def cancel_request_reminder(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(RequestCancelled)
    await CancelTripReminders(SQLAlchemyReminderStore(session)).for_request(data.request_id)


async def cancel_declined_reminder(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(RequestDeclined)
    if data.was_accepted:  # a pending request never had a reminder
        await CancelTripReminders(SQLAlchemyReminderStore(session)).for_request(data.request_id)


async def cancel_trip_reminders(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(TripCancelled)
    await CancelTripReminders(SQLAlchemyReminderStore(session)).for_trip(data.trip_id)


def reminder_handlers(lead: timedelta) -> HandlerMap:
    """The reminder handlers, by event. ``lead``: how long before departure riders are
    reminded (``NOTIFICATIONS_REMINDER_LEAD_MINUTES``)."""

    async def schedule_reminder(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(RequestAccepted)
        await ScheduleTripReminder(SQLAlchemyReminderStore(session), lead).execute(
            rider_id=data.rider_id,
            trip_id=data.trip_id,
            request_id=data.request_id,
            departure_at=data.departure_at,
            pickup_label=data.pickup_label,
            driver_id=data.driver_id,
        )

    return {
        RequestAccepted: schedule_reminder,
        RequestCancelled: cancel_request_reminder,
        RequestDeclined: cancel_declined_reminder,
        TripCancelled: cancel_trip_reminders,
    }


def register_reminder_handlers(consumer: StreamConsumer, lead: timedelta) -> None:
    """Only the reminders, on a consumer of their own (tests). The service registers them
    together with the notifications (``registration.register_event_handlers``)."""
    register_event_handlers(consumer, reminder_handlers(lead))
