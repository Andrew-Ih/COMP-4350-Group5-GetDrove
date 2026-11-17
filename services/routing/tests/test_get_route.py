"""Unit tests for the GetRoute application use case (#123, #135)."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.get_route import GetRoute
from routing.domain.entities import Route
from routing.domain.errors import RouteNotFoundError
from routing.domain.values import Direction, LatLng, RouteSample

DRIVER = uuid4()
ROUTE = Route(
    trip_id=uuid4(),
    path=(LatLng(lat=49.876812, lng=-97.143807), LatLng(lat=49.8075, lng=-97.1366)),
    distance_meters=8832,
    duration_seconds=793,
    driver_id=DRIVER,
    direction=Direction.TO_CAMPUS,
)


class FakeRepository:
    def __init__(self, *stored: Route) -> None:
        self.routes = {route.trip_id: route for route in stored}

    async def save(self, route: Route, samples: Sequence[RouteSample]) -> None:
        self.routes[route.trip_id] = route

    async def get(self, trip_id: UUID) -> Route | None:
        return self.routes.get(trip_id)


async def test_the_driver_gets_the_stored_route() -> None:
    assert await GetRoute(FakeRepository(ROUTE)).execute(ROUTE.trip_id, DRIVER) == ROUTE


async def test_anyone_else_gets_it_without_the_drivers_end() -> None:
    seen = await GetRoute(FakeRepository(ROUTE)).execute(ROUTE.trip_id, uuid4())

    assert seen.path[0] != ROUTE.path[0]  # the driver's start is cut off
    assert seen.path[-1] == ROUTE.path[-1]  # the campus end stays
    # Everything else is the trip's own.
    assert (seen.trip_id, seen.distance_meters, seen.duration_seconds) == (
        ROUTE.trip_id,
        ROUTE.distance_meters,
        ROUTE.duration_seconds,
    )


async def test_unknown_trip_is_not_found() -> None:
    with pytest.raises(RouteNotFoundError):
        await GetRoute(FakeRepository(ROUTE)).execute(uuid4(), DRIVER)
