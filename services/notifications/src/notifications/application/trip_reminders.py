"""Use cases: schedule a rider's trip reminder when they are accepted, and cancel it when
the request or the trip is cancelled (#148). Sending them is #149."""

from datetime import datetime
from uuid import UUID

from notifications.application.ports import ReminderStore
from notifications.domain.reminders import TripReminder


class ScheduleTripReminder:
    def __init__(self, store: ReminderStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        rider_id: UUID,
        trip_id: UUID,
        request_id: UUID,
        departure_at: datetime,
        pickup_label: str,
    ) -> bool:
        """Returns False if the request already had a reminder (nothing changes)."""
        reminder = TripReminder.for_accepted_request(
            rider_id=rider_id,
            trip_id=trip_id,
            request_id=request_id,
            departure_at=departure_at,
            pickup_label=pickup_label,
        )
        return await self._store.add(reminder)


class CancelTripReminders:
    """Only pending reminders are cancelled; one already sent stays sent."""

    def __init__(self, store: ReminderStore) -> None:
        self._store = store

    async def for_request(self, request_id: UUID) -> int:
        return await self._store.cancel_for_request(request_id)

    async def for_trip(self, trip_id: UUID) -> int:
        return await self._store.cancel_for_trip(trip_id)
