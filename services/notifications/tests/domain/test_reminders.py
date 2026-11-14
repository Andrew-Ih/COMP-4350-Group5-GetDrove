"""When a trip reminder is due (#148)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from notifications.domain.reminders import (
    REMINDER_LEAD,
    ReminderStatus,
    TripReminder,
    reminder_due_at,
)

DEPARTURE = datetime(2026, 11, 16, 7, 45, tzinfo=UTC)


def reminder() -> TripReminder:
    return TripReminder.for_accepted_request(
        rider_id=uuid4(),
        trip_id=uuid4(),
        request_id=uuid4(),
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
    )


def test_the_reminder_is_due_30_minutes_before_departure() -> None:
    assert timedelta(minutes=30) == REMINDER_LEAD
    assert reminder_due_at(DEPARTURE) == datetime(2026, 11, 16, 7, 15, tzinfo=UTC)


def test_a_new_reminder_is_pending_with_its_own_id() -> None:
    first, second = reminder(), reminder()

    assert first.status is ReminderStatus.PENDING
    assert first.send_at == reminder_due_at(DEPARTURE)
    assert first.id != second.id
