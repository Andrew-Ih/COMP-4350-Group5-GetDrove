"""Unit tests for the Route entity."""

from uuid import uuid4

import pytest

from routing.domain.entities import Route
from routing.domain.values import LatLng

HOME = LatLng(lat=49.82, lng=-97.15)
CAMPUS = LatLng(lat=49.8075, lng=-97.1366)


@pytest.mark.parametrize("distance,duration", [(6000, 900), (0, 0)])
def test_valid_route(distance: int, duration: int) -> None:
    route = Route(
        trip_id=uuid4(),
        path=(HOME, CAMPUS),
        distance_meters=distance,
        duration_seconds=duration,
    )

    assert route.path == (HOME, CAMPUS)


@pytest.mark.parametrize(
    "path,distance,duration,message",
    [
        ((), 6000, 900, "at least two points"),
        ((HOME,), 6000, 900, "at least two points"),
        ((HOME, CAMPUS), -1, 900, "Distance"),
        ((HOME, CAMPUS), 6000, -1, "Duration"),
    ],
)
def test_invalid_route(
    path: tuple[LatLng, ...], distance: int, duration: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Route(trip_id=uuid4(), path=path, distance_meters=distance, duration_seconds=duration)
