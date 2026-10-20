"""POST /internal/matches with a real PostgreSQL database and a mocked OSRM (#25, #26)."""

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
from routing.application.match_rider import DEFAULT_PICKUP_LABEL
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import Corridor, LatLng
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("routing_database")

type Handler = Callable[[httpx.Request], httpx.Response]

# About 300 m north of the middle of the "near" route below.
RIDER = {"lat": 49.8527, "lng": -97.179}
WALKING_SPEED = 1.39  # m/s: OSRM's foot profile


def east_west(lat: float) -> Route:
    """A 3 km route due east along a line of latitude."""
    west, east = LatLng(lat=lat, lng=-97.20), LatLng(lat=lat, lng=-97.158)
    return Route(
        trip_id=uuid4(),
        path=(west, east),
        distance_meters=round(distance_meters(west, east)),
        duration_seconds=300,
    )


class API:
    def __init__(self, app: FastAPI, engine: AsyncEngine) -> None:
        self.app, self.engine = app, engine
        self.near, self.far = east_west(49.85), east_west(49.87)  # far: about 2 km north
        self.osrm_requests: list[httpx.Request] = []


@pytest.fixture
async def api() -> AsyncIterator[API]:
    app = create_app()
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.corridor = Corridor(radius_meters=800)
    app.state.max_walk_seconds = 600
    api = API(app, engine)
    try:
        async with app.state.session_factory() as session, session.begin():
            repository = SQLAlchemyRouteRepository(session)
            for route in (api.near, api.far):
                await repository.save(route, sample_route(route))
        yield api
    finally:
        # Deleting the routes deletes their samples too.
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(routes).where(routes.c.trip_id.in_([api.near.trip_id, api.far.trip_id]))
                )
        finally:
            await engine.dispose()


def foot(detour: float = 1.3) -> Handler:
    """OSRM's table service, walking ``detour`` times the straight-line distance."""

    def handler(request: httpx.Request) -> httpx.Response:
        coordinates = request.url.path.removeprefix("/table/v1/foot/").split(";")
        rider, *destinations = (
            LatLng(lat=float(lat), lng=float(lng))
            for lng, lat in (pair.split(",") for pair in coordinates)
        )
        meters = [0.0] + [distance_meters(rider, d) * detour for d in destinations]
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "durations": [[m / WALKING_SPEED for m in meters]],
                "distances": [meters],
            },
        )

    return handler


def car(request: httpx.Request) -> httpx.Response:
    """OSRM's nearest service, for the pickup label."""
    return httpx.Response(200, json={"code": "Ok", "waypoints": [{"name": "Pembina Highway"}]})


async def post(api: API, body: dict[str, Any], foot: Handler, car: Handler = car) -> httpx.Response:
    def recording(handler: Handler) -> Handler:
        def record(request: httpx.Request) -> httpx.Response:
            api.osrm_requests.append(request)
            return handler(request)

        return record

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(recording(foot)), base_url="http://osrm-foot:5000"
        ) as foot_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(recording(car)), base_url="http://osrm-car:5000"
        ) as car_client,
    ):
        api.app.state.osrm_foot_client = foot_client
        api.app.state.osrm_car_client = car_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post("/internal/matches", json=body)


def request(*trip_ids: UUID) -> dict[str, Any]:
    return {"rider": RIDER, "tripIds": [str(trip_id) for trip_id in trip_ids]}


async def test_a_trip_passing_near_the_rider_matches(api: API) -> None:
    response = await post(api, request(api.near.trip_id), foot())

    assert response.status_code == 200, response.text
    [match] = response.json()["matches"]
    assert match["tripId"] == str(api.near.trip_id)
    # The pickup is the point on the route beside the rider.
    assert match["pickup"]["label"] == "Pembina Highway"
    assert match["pickup"]["lat"] == pytest.approx(49.85)
    assert match["pickup"]["lng"] == pytest.approx(RIDER["lng"], abs=0.001)
    # About 300 m in a straight line, 390 m on foot: under 5 minutes.
    assert match["walkSeconds"] == pytest.approx(390 / WALKING_SPEED, abs=40)
    # Picked up halfway, the rider rides the second half of the route.
    assert match["riderDistanceMeters"] == pytest.approx(api.near.distance_meters / 2, abs=100)


async def test_only_trips_the_rider_can_walk_to_match(api: API) -> None:
    unknown = uuid4()

    response = await post(api, request(api.far.trip_id, unknown, api.near.trip_id), foot())

    assert response.status_code == 200, response.text
    assert [m["tripId"] for m in response.json()["matches"]] == [str(api.near.trip_id)]


async def test_a_rider_across_the_river_does_not_match(api: API) -> None:
    """Inside the corridor, but walking there means a long way round to a bridge."""
    response = await post(api, request(api.near.trip_id), foot(detour=5))

    assert response.status_code == 200, response.text
    assert response.json() == {"matches": []}


async def test_no_candidate_trips_is_an_empty_result(api: API) -> None:
    response = await post(api, request(), foot())

    assert response.status_code == 200
    assert response.json() == {"matches": []}
    assert api.osrm_requests == []


async def test_walking_engine_down_returns_503(api: API) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OSRM is not running", request=request)

    response = await post(api, request(api.near.trip_id), down)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_engine_unavailable"


async def test_no_road_name_still_matches_with_the_default_label(api: API) -> None:
    def no_name(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"code": "Error"})

    response = await post(api, request(api.near.trip_id), foot(), car=no_name)

    assert response.status_code == 200, response.text
    assert response.json()["matches"][0]["pickup"]["label"] == DEFAULT_PICKUP_LABEL


@pytest.mark.parametrize(
    "body",
    [
        {"rider": {"lat": 120, "lng": -97.14}, "tripIds": []},
        {"rider": {"lat": 49.85, "lng": -200}, "tripIds": []},
        {"rider": RIDER, "tripIds": ["not-a-uuid"]},
        {"rider": RIDER, "tripIds": [str(uuid4()) for _ in range(501)]},
        {"tripIds": []},
    ],
)
async def test_invalid_input_returns_422_without_calling_osrm(
    api: API, body: dict[str, Any]
) -> None:
    response = await post(api, body, foot())

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert api.osrm_requests == []


def test_walking_speed_matches_the_default_limit() -> None:
    """10 minutes at OSRM's walking speed is a little over the corridor's 800 m."""
    settings = get_settings()
    assert settings.corridor_meters == 800
    assert settings.corridor_meters < settings.max_walk_seconds * WALKING_SPEED < 900
