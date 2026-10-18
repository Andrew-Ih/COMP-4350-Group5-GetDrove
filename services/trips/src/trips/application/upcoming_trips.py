
"""Application use case for listing a driver's upcoming trips."""

from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import TripRepository
from trips.domain.entities import Trip


class ListUpcomingTrips:
    def __init__(self, repository: TripRepository) -> None:
        self.repository = repository

    async def execute(self, driver_id: UUID) -> list[Trip]:
        return await self.repository.get_upcoming_by_driver(
            driver_id=driver_id,
            now=datetime.now(UTC),
        )
