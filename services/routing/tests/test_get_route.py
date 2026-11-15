"""Unit tests for the GetRoute application use case."""

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from routing.application.get_route import GetRoute
from routing.domain.entities import Route
from routing.domain.errors import RouteNotFoundError
from routing.domain.values import LatLng, RouteSample

ROUTE = Route(
    trip_id=uuid4(),
    path=(LatLng(lat=49.82, lng=-97.15), LatLng(lat=49.8075, lng=-97.1366)),
    distance_meters=6000,
    duration_seconds=900,
)


class FakeRepository:
    def __init__(self, *stored: Route) -> None:
        self.routes = {route.trip_id: route for route in stored}

    async def save(self, route: Route, samples: Sequence[RouteSample]) -> None:
        self.routes[route.trip_id] = route

    async def get(self, trip_id: UUID) -> Route | None:
        return self.routes.get(trip_id)


async def test_get_route_returns_the_stored_route() -> None:
    assert await GetRoute(FakeRepository(ROUTE)).execute(ROUTE.trip_id) == ROUTE


async def test_unknown_trip_is_not_found() -> None:
    with pytest.raises(RouteNotFoundError):
        await GetRoute(FakeRepository(ROUTE)).execute(uuid4())
