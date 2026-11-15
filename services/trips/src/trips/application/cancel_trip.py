"""Application use case for cancelling a single trip."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import TripCancellationEvents, TripCancellationRepository
from trips.domain.entities import Trip
from trips.domain.errors import TripNotFoundError


class CancelTrip:
    def __init__(
        self,
        repository: TripCancellationRepository,
        events: TripCancellationEvents,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.events = events
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, *, trip_id: UUID, driver_id: UUID) -> Trip:
        trip = await self.repository.get_for_update(trip_id)
        if trip is None:
            raise TripNotFoundError()

        cancelled_at = self.clock()
        is_late = trip.cancel(driver_id, cancelled_at)
        rider_ids = await self.repository.save_cancellation(trip, cancelled_at)
        await self.events.trip_cancelled(trip, rider_ids)
        if is_late:
            await self.events.driver_late_cancellation(trip, cancelled_at)
        return trip
