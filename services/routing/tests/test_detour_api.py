"""POST /internal/detours with a real PostgreSQL database and a mocked OSRM (#36)."""

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import LatLng
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("routing_database")

type Handler = Callable[[httpx.Request], httpx.Response]

DRIVING_SPEED = 10.0  # m/s
DETOUR_TIMEOUT = 0.8

WEST, EAST = LatLng(lat=49.85, lng=-97.20), LatLng(lat=49.85, lng=-97.158)
FIRST, SECOND = {"lat": 49.85, "lng": -97.19}, {"lat": 49.85, "lng": -97.17}
# Beside the route, between the two accepted pickups.
BETWEEN = {"lat": 49.851, "lng": -97.18}


def east_west() -> Route:
    """A 3 km route due east along a line of latitude."""
    return Route(
        trip_id=uuid4(),
        path=(WEST, EAST),
        distance_meters=round(distance_meters(WEST, EAST)),
        duration_seconds=300,
    )


class API:
    def __init__(self, app: FastAPI, engine: AsyncEngine, route: Route) -> None:
        self.app, self.engine, self.route = app, engine, route
        self.osrm_requests: list[httpx.Request] = []


@pytest.fixture
async def api() -> AsyncIterator[API]:
    app = create_app()
    engine = create_async_engine(get_settings().database_url)
    app.state.detour_plans = MemoryPlans()
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.detour_timeout_seconds = DETOUR_TIMEOUT
    route = east_west()
    try:
        async with app.state.session_factory() as session, session.begin():
            await SQLAlchemyRouteRepository(session).save(route, sample_route(route))
        yield API(app, engine, route)
    finally:
        # Deleting the route deletes its samples too.
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(routes).where(routes.c.trip_id == route.trip_id))
        finally:
            await engine.dispose()


def points_in(request: httpx.Request) -> list[LatLng]:
    coordinates = request.url.path.removeprefix("/table/v1/driving/").split(";")
    return [
        LatLng(lat=float(lat), lng=float(lng))
        for lng, lat in (pair.split(",") for pair in coordinates)
    ]


class MemoryPlans:
    def __init__(self) -> None:
        self.plans: dict[tuple[UUID, str], list[list[float]]] = {}

    async def get(self, trip_id: UUID, key: str) -> list[list[float]] | None:
        return self.plans.get((trip_id, key))

    async def put(self, trip_id: UUID, key: str, matrix: list[list[float]]) -> None:
        self.plans[(trip_id, key)] = matrix

    async def forget(self, trip_id: UUID) -> None:
        self.plans = {k: v for k, v in self.plans.items() if k[0] != trip_id}


def driving(request: httpx.Request) -> httpx.Response:
    """OSRM's table service, driving at 10 m/s in a straight line between any two points,
    for the ``sources`` and ``destinations`` asked for (all points if none)."""
    points = points_in(request)

    def indexes(name: str) -> list[int]:
        value = request.url.params.get(name)
        return list(range(len(points))) if value is None else [int(i) for i in value.split(";")]

    durations = [
        [distance_meters(points[i], points[j]) / DRIVING_SPEED for j in indexes("destinations")]
        for i in indexes("sources")
    ]
    return httpx.Response(200, json={"code": "Ok", "durations": durations})


async def call(api: API, body: dict[str, Any], car: Handler) -> httpx.Response:
    def recording(request: httpx.Request) -> httpx.Response:
        api.osrm_requests.append(request)
        return car(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(recording), base_url="http://osrm-car:5000"
    ) as car_client:
        api.app.state.osrm_car_client = car_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post("/internal/detours", json=body)


def detour_request(api: API, **change: Any) -> dict[str, Any]:
    return {
        "tripId": str(api.route.trip_id),
        "acceptedPickups": [FIRST, SECOND],
        "newPickup": BETWEEN,
        **change,
    }


async def test_a_pickup_between_two_others_goes_between_them(api: API) -> None:
    response = await call(api, detour_request(api), driving)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["position"] == 1
    assert result["addedSeconds"] > 0  # it's 110 m off the road
    # The trip as it stands (3 km at 10 m/s) plus what the new pickup adds.
    base = distance_meters(WEST, EAST) / DRIVING_SPEED
    assert result["totalSeconds"] == pytest.approx(base + result["addedSeconds"], abs=1)


async def test_asks_osrm_once_for_the_route_ends_and_every_pickup(api: API) -> None:
    await call(api, detour_request(api), driving)

    [request] = api.osrm_requests
    # The route's start, the accepted pickups in order, the new pickup, the route's end.
    assert points_in(request) == [
        WEST,
        LatLng(**FIRST),
        LatLng(**SECOND),
        LatLng(**BETWEEN),
        EAST,
    ]


async def test_waits_for_osrm_only_as_long_as_the_detour_timeout(api: API) -> None:
    await call(api, detour_request(api), driving)

    [request] = api.osrm_requests
    assert request.extensions["timeout"]["read"] == DETOUR_TIMEOUT


async def test_the_first_rider_has_nothing_to_go_around(api: API) -> None:
    response = await call(api, detour_request(api, acceptedPickups=[]), driving)

    assert response.status_code == 200, response.text
    assert response.json()["position"] == 0


async def test_unknown_trip_returns_404_without_calling_osrm(api: API) -> None:
    response = await call(api, detour_request(api, tripId=str(uuid4())), driving)

    assert response.status_code == 404
    assert response.json()["code"] == "route_not_found"
    assert api.osrm_requests == []


async def test_routing_engine_down_returns_503(api: API) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OSRM is not running", request=request)

    response = await call(api, detour_request(api), down)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_engine_unavailable"


async def test_a_pair_with_no_route_returns_503_not_a_wrong_number(api: API) -> None:
    def no_route(request: httpx.Request) -> httpx.Response:
        body = driving(request).json()
        body["durations"][0][2] = None
        return httpx.Response(200, json=body)

    response = await call(api, detour_request(api), no_route)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_engine_unavailable"


@pytest.mark.parametrize(
    "change",
    [
        {"acceptedPickups": [FIRST] * 7},
        {"newPickup": {"lat": 91, "lng": 0}},
        {"newPickup": None},
        {"tripId": "not-a-uuid"},
    ],
)
async def test_invalid_input_returns_422_without_calling_osrm(
    api: API, change: dict[str, Any]
) -> None:
    response = await call(api, detour_request(api, **change), driving)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert api.osrm_requests == []


async def test_a_second_quote_uses_the_saved_plan_and_gives_the_same_answer(api: API) -> None:
    first = await call(api, detour_request(api), driving)
    second = await call(api, detour_request(api), driving)

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    # One full matrix for the first quote; the second only asks for the new pickup's row
    # and column.
    assert len(api.osrm_requests) == 3
    assert "sources" not in api.osrm_requests[0].url.params
    assert all("sources" in r.url.params for r in api.osrm_requests[1:])
