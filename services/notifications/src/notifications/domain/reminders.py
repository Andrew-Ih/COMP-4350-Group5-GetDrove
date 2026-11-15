"""Trip reminders (#148): a rider with a seat is reminded shortly before departure.

A reminder is stored when the rider is accepted (``RequestAccepted``) and sent by the
scheduler (#149) once it is due. If the request or the trip is cancelled first, the
reminder is cancelled and never sent.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4


class ScheduledNotificationType(StrEnum):
    """What a scheduled notification is. Only trip reminders so far; the table is shared, so
    later kinds can be added here."""

    TRIP_REMINDER = "trip_reminder"


class ReminderStatus(StrEnum):
    PENDING = "pending"  # waiting to be sent
    SENT = "sent"
    SKIPPED = "skipped"  # the trip had already left when it was due (e.g. after an outage)
    CANCELLED = "cancelled"  # the request or the trip was cancelled first


def reminder_due_at(departure_at: datetime, lead: timedelta) -> datetime:
    """``lead`` before departure (``NOTIFICATIONS_REMINDER_LEAD_MINUTES``, 30 by default).
    A rider accepted later than that gets a reminder that is already due, so the scheduler
    sends it on its next pass."""
    return departure_at - lead


@dataclass(frozen=True)
class TripReminder:
    """One accepted rider's reminder for one trip."""

    rider_id: UUID
    trip_id: UUID
    request_id: UUID
    departure_at: datetime
    pickup_label: str  # the pickup point's label, never the rider's own location
    send_at: datetime
    # The trip's driver, so the reminder can say who's picking them up (#149). None for
    # reminders stored before it was kept.
    driver_id: UUID | None = None
    status: ReminderStatus = ReminderStatus.PENDING
    type: ScheduledNotificationType = ScheduledNotificationType.TRIP_REMINDER
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def for_accepted_request(
        cls,
        *,
        rider_id: UUID,
        trip_id: UUID,
        request_id: UUID,
        departure_at: datetime,
        pickup_label: str,
        lead: timedelta,
        driver_id: UUID | None = None,
    ) -> "TripReminder":
        return cls(
            rider_id=rider_id,
            trip_id=trip_id,
            request_id=request_id,
            departure_at=departure_at,
            pickup_label=pickup_label,
            send_at=reminder_due_at(departure_at, lead),
            driver_id=driver_id,
        )


def has_departed(reminder: TripReminder, now: datetime) -> bool:
    """Too late to remind: the trip has left (e.g. Notifications was down when the reminder
    was due, #149). Such a reminder is skipped, not sent."""
    return reminder.departure_at <= now
