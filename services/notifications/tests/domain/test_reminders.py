"""When a trip reminder is due (#148)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from notifications.domain.reminders import (
    ReminderStatus,
    ScheduledNotificationType,
    TripReminder,
    reminder_due_at,
)

DEPARTURE = datetime(2026, 11, 16, 7, 45, tzinfo=UTC)
LEAD = timedelta(minutes=30)


def reminder() -> TripReminder:
    return TripReminder.for_accepted_request(
        rider_id=uuid4(),
        trip_id=uuid4(),
        request_id=uuid4(),
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        lead=LEAD,
    )


def test_the_reminder_is_due_the_lead_time_before_departure() -> None:
    assert reminder_due_at(DEPARTURE, LEAD) == datetime(2026, 11, 16, 7, 15, tzinfo=UTC)
    assert reminder_due_at(DEPARTURE, timedelta(minutes=45)) == datetime(
        2026, 11, 16, 7, 0, tzinfo=UTC
    )


def test_a_new_reminder_is_a_pending_trip_reminder_with_its_own_id() -> None:
    first, second = reminder(), reminder()

    assert first.status is ReminderStatus.PENDING
    assert first.type is ScheduledNotificationType.TRIP_REMINDER
    assert first.send_at == reminder_due_at(DEPARTURE, LEAD)
    assert first.id != second.id
