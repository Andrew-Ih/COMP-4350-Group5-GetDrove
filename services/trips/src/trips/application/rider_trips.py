"""Application use case for listing a rider's trip requests."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import RiderTripRepository
from trips.domain.entities import Trip
from trips.domain.seat_request import SeatRequest


class ListRiderTrips:
    def __init__(
        self,
        repository: RiderTripRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, rider_id: UUID, *, past: bool) -> list[tuple[Trip, SeatRequest]]:
        return await self.repository.list_by_rider(rider_id, self.clock(), past=past)
