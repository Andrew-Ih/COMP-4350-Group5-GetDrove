
"""Application use case for listing a driver's upcoming trips."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import TripRepository
from trips.domain.entities import Trip


class ListUpcomingTrips:
    def __init__(
        self,
        repository: TripRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, driver_id: UUID) -> list[Trip]:
        return await self.repository.get_upcoming_by_driver(
            driver_id=driver_id,
            now=self.clock(),
        )
