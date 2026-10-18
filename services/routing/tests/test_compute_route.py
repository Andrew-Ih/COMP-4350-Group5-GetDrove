"""Unit tests for the ComputeRoute application use case."""

from uuid import uuid4

import pytest

from routing.application.compute_route import ComputeRoute
from routing.application.ports import DrivingRoute
from routing.domain.entities import Route
from routing.domain.errors import NoRouteError, RoutingEngineUnavailableError
from routing.domain.values import LatLng

HOME = LatLng(lat=49.82, lng=-97.15)
CAMPUS = LatLng(lat=49.8075, lng=-97.1366)
PATH = (HOME, LatLng(lat=49.815, lng=-97.14), CAMPUS)


class FakeEngine:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[LatLng, LatLng]] = []

    async def driving_route(self, origin: LatLng, destination: LatLng) -> DrivingRoute:
        self.calls.append((origin, destination))
        if self.error:
            raise self.error
        return DrivingRoute(path=PATH, distance_meters=6000, duration_seconds=900)


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[Route] = []

    async def save(self, route: Route) -> None:
        self.saved.append(route)


async def test_compute_route_stores_and_returns_the_route() -> None:
    engine = FakeEngine()
    repository = FakeRepository()
    trip_id = uuid4()

    route = await ComputeRoute(engine, repository).execute(
        trip_id=trip_id, origin=HOME, destination=CAMPUS
    )

    assert engine.calls == [(HOME, CAMPUS)]
    assert repository.saved == [route]
    assert route == Route(trip_id=trip_id, path=PATH, distance_meters=6000, duration_seconds=900)


@pytest.mark.parametrize("error", [NoRouteError(), RoutingEngineUnavailableError()])
async def test_engine_failure_saves_nothing(error: Exception) -> None:
    repository = FakeRepository()

    with pytest.raises(type(error)):
        await ComputeRoute(FakeEngine(error), repository).execute(
            trip_id=uuid4(), origin=HOME, destination=CAMPUS
        )

    assert repository.saved == []
