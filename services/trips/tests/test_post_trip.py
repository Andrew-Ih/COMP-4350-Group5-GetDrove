"""Unit tests for the PostTrip application use case."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from trips.application.ports import RouteEstimate
from trips.application.post_trip import (
    DepartureInPastError,
    PostTrip,
)
from trips.domain.entities import Trip
from trips.domain.values import CAMPUS, Direction, Location

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[Trip] = []

    async def add(self, trip: Trip) -> None:
        self.saved.append(trip)

    async def get_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]:
        return []


class FakeEvents:
    def __init__(self) -> None:
        self.posted: list[UUID] = []

    async def trip_posted(self, trip_id: UUID) -> None:
        self.posted.append(trip_id)


class FakeRouting:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, Location, Location]] = []

    async def compute_route(
        self,
        trip_id: UUID,
        origin: Location,
        destination: Location,
    ) -> RouteEstimate:
        self.calls.append((trip_id, origin, destination))
        return RouteEstimate(
            distance_meters=6000,
            duration_seconds=900,
        )


@pytest.mark.parametrize(
    "direction",
    [Direction.TO_CAMPUS, Direction.FROM_CAMPUS],
)
async def test_post_trip(direction: Direction) -> None:
    repository = FakeRepository()
    routing = FakeRouting()
    events = FakeEvents()
    use_case = PostTrip(repository, routing, events, clock=lambda: NOW)

    place = Location("Pembina Highway", 49.82, -97.15)
    departure = NOW + timedelta(hours=2)

    trip = await use_case.execute(
        driver_id=uuid4(),
        direction=direction,
        place=place,
        departure_at=departure,
        seats_total=3,
    )

    assert repository.saved == [trip]
    assert events.posted == [trip.id]
    assert trip.seats_available == 3
    assert trip.distance_meters == 6000
    assert trip.duration_seconds == 900
    assert trip.estimated_arrival_at == departure + timedelta(minutes=15)

    route_id, origin, destination = routing.calls[0]
    assert route_id == trip.id

    if direction == Direction.TO_CAMPUS:
        assert origin == place
        assert destination == CAMPUS
    else:
        assert origin == CAMPUS
        assert destination == place


@pytest.mark.parametrize("departure", [NOW - timedelta(hours=1), NOW, NOW.replace(tzinfo=None)])
async def test_reject_past_departure(departure: datetime) -> None:
    repository = FakeRepository()
    routing = FakeRouting()
    events = FakeEvents()
    use_case = PostTrip(repository, routing, events, clock=lambda: NOW)

    with pytest.raises(DepartureInPastError):
        await use_case.execute(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=Location("Pembina Highway", 49.82, -97.15),
            departure_at=departure,
            seats_total=3,
        )

    assert repository.saved == []
    assert events.posted == []
    assert routing.calls == []
