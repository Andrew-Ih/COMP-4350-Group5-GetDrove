"""Handlers that keep trip reminders in step with Trips' events (#148).

- ``RequestAccepted``: schedule the rider's reminder, 30 minutes before departure.
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

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from notifications.adapters.persistence.reminder_store import SQLAlchemyReminderStore
from notifications.application.trip_reminders import CancelTripReminders, ScheduleTripReminder


async def schedule_reminder(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(RequestAccepted)
    await ScheduleTripReminder(SQLAlchemyReminderStore(session)).execute(
        rider_id=data.rider_id,
        trip_id=data.trip_id,
        request_id=data.request_id,
        departure_at=data.departure_at,
        pickup_label=data.pickup_label,
    )


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


def register_reminder_handlers(consumer: StreamConsumer) -> None:
    consumer.on(RequestAccepted)(schedule_reminder)
    consumer.on(RequestCancelled)(cancel_request_reminder)
    consumer.on(RequestDeclined)(cancel_declined_reminder)
    consumer.on(TripCancelled)(cancel_trip_reminders)
