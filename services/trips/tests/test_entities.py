from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from trips.domain.entities import Trip
from trips.domain.values import CAMPUS, Direction, Location, TripStatus


@pytest.fixture
def place() -> Location:
    return Location(
        label="Pembina Highway",
        lat=49.82,
        lng=-97.15,
    )


def test_create_trip_to_campus(place: Location) -> None:
    departure = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)

    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=place,
        departure_at=departure,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )

    assert trip.origin == place
    assert trip.destination == CAMPUS
    assert trip.estimated_arrival_at == departure + timedelta(minutes=15)
    assert trip.seats_total == 3
    assert trip.seats_available == 3
    assert trip.status == TripStatus.SCHEDULED


def test_create_trip_from_campus(place: Location) -> None:
    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.FROM_CAMPUS,
        place=place,
        departure_at=datetime(2026, 10, 20, 8, 0, tzinfo=UTC),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=2,
    )

    assert trip.origin == CAMPUS
    assert trip.destination == place


@pytest.mark.parametrize("seats", [0, -1, 7])
def test_reject_invalid_seats(place: Location, seats: int) -> None:
    with pytest.raises(ValueError, match="Seats must be between 1 and 6"):
        Trip.create(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=datetime(2026, 10, 20, 8, 0, tzinfo=UTC),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=seats,
        )


@pytest.mark.parametrize(
    ("duration", "distance"),
    [(-1, 6000), (900, -1)],
)
def test_reject_negative_route_values(
    place: Location,
    duration: int,
    distance: int,
) -> None:
    with pytest.raises(ValueError):
        Trip.create(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=datetime(2026, 10, 20, 8, 0, tzinfo=UTC),
            duration_seconds=duration,
            distance_meters=distance,
            seats_total=3,
        )


def test_reject_naive_departure(place: Location) -> None:
    with pytest.raises(ValueError, match="timezone"):
        Trip.create(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=datetime(2026, 10, 20, 8, 0),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )
