"""Unit tests for the ListUpcomingTrips use case."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from trips.application.upcoming_trips import ListUpcomingTrips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location


@pytest.mark.asyncio
@pytest.mark.parametrize("past", [False, True])
async def test_execute_passes_driver_id_and_current_time_to_repository(past: bool) -> None:
    driver_id = uuid4()
    now = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)

    trip = Trip.create(
        driver_id=driver_id,
        direction=Direction.TO_CAMPUS,
        place=Location(
            label="Pembina Highway",
            lat=49.82,
            lng=-97.15,
        ),
        departure_at=datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )

    class FakeRepository:
        def __init__(self) -> None:
            self.received_driver_id: UUID | None = None
            self.received_now: datetime | None = None

        async def list_by_driver(self, *, driver_id: UUID, now: datetime, past: bool) -> list[Trip]:
            self.received_past = past
            self.received_driver_id = driver_id
            self.received_now = now
            return [trip]

    repository = FakeRepository()
    service = ListUpcomingTrips(repository, clock=lambda: now)

    result = await service.execute(driver_id=driver_id, past=past)

    assert result == [trip]
    assert repository.received_driver_id == driver_id
    assert repository.received_now == now
    assert repository.received_past is past
