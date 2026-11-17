"""POST /internal/pickup-points with a real PostgreSQL database and a mocked OSRM (#29)."""

from collections.abc import AsyncIterator, Callable
from itertools import pairwise
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.application.pickups import DEFAULT_PICKUP_LABEL
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.values import Corridor, LatLng
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("routing_database")

type Handler = Callable[[httpx.Request], httpx.Response]

# About 300 m north of the middle of the route below.
RIDER = {"lat": 49.8527, "lng": -97.179}
WALKING_SPEED = 1.39  # m/s: OSRM's foot profile

WEST, EAST = LatLng(lat=49.85, lng=-97.20), LatLng(lat=49.85, lng=-97.158)


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
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.corridor = Corridor(radius_meters=800)
    app.state.max_walk_seconds = 600
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


def car(name: str) -> Handler:
    """OSRM's nearest service, for pickup labels: every point is on this road."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"code": "Ok", "waypoints": [{"name": name, "distance": 5}]}
        )

    return handler


on_pembina = car("Pembina Highway")


async def call(
    api: API,
    path: str,
    body: dict[str, Any],
    foot: Handler,
    car: Handler | None = None,
) -> httpx.Response:
    car = car or on_pembina

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
            return await client.post(path, json=body)


def pickups_request(api: API, **change: Any) -> dict[str, Any]:
    return {"tripId": str(api.route.trip_id), "rider": RIDER, **change}


async def test_returns_ranked_pickup_points(api: API) -> None:
    response = await call(api, "/internal/pickup-points", pickups_request(api), foot())

    assert response.status_code == 200, response.text
    pickups = response.json()["pickups"]
    assert len(pickups) == 3  # the default limit
    walks = [p["walkSeconds"] for p in pickups]
    assert walks == sorted(walks)  # shortest walk first
    first = pickups[0]
    assert first["id"].startswith("s")
    assert first["label"] == "Pembina Highway"
    # The nearest is the point on the route beside the rider, about halfway along.
    assert first["lat"] == pytest.approx(49.85)
    assert first["lng"] == pytest.approx(RIDER["lng"], abs=0.002)
    assert first["riderDistanceMeters"] == pytest.approx(api.route.distance_meters / 2, abs=150)
    # Three different points, spread out along the route.
    assert len({p["id"] for p in pickups}) == 3
    offsets = sorted(p["riderDistanceMeters"] for p in pickups)
    assert all(b - a >= 200 for a, b in pairwise(offsets))


async def test_the_first_point_is_what_search_offers(api: API) -> None:
    """#30: the trip detail and search show the same point for the same trip and spot."""
    body = pickups_request(api, limit=1)
    [pickup] = (await call(api, "/internal/pickup-points", body, foot())).json()["pickups"]

    search = {"rider": RIDER, "tripIds": [str(api.route.trip_id)]}
    [match] = (await call(api, "/internal/matches", search, foot())).json()["matches"]

    assert (match["pickup"]["lat"], match["pickup"]["lng"]) == (pickup["lat"], pickup["lng"])
    assert match["pickup"]["label"] == pickup["label"]
    assert match["walkSeconds"] == pickup["walkSeconds"]
    assert match["riderDistanceMeters"] == pickup["riderDistanceMeters"]


async def test_limit_caps_the_number_of_points(api: API) -> None:
    response = await call(api, "/internal/pickup-points", pickups_request(api, limit=1), foot())

    assert len(response.json()["pickups"]) == 1


async def test_rejected_points_are_never_returned_again(api: API) -> None:
    """#29 / #136: the rider rejects the suggestions; asking again with their IDs in
    `exclude` brings different points, never the rejected ones."""
    first = (await call(api, "/internal/pickup-points", pickups_request(api), foot())).json()
    rejected = [p["id"] for p in first["pickups"]]

    body = pickups_request(api, exclude=rejected)
    response = await call(api, "/internal/pickup-points", body, foot())

    assert response.status_code == 200, response.text
    again = response.json()["pickups"]
    assert again  # the route still has other points within walking distance
    assert not {p["id"] for p in again} & set(rejected)
    walks = [p["walkSeconds"] for p in again]
    assert walks == sorted(walks)


async def test_exclude_with_unknown_ids_changes_nothing(api: API) -> None:
    plain = (await call(api, "/internal/pickup-points", pickups_request(api), foot())).json()

    body = pickups_request(api, exclude=["s9999"])
    with_unknown = (await call(api, "/internal/pickup-points", body, foot())).json()

    assert with_unknown == plain


async def test_points_on_excluded_roads_are_never_returned(api: API) -> None:
    on_bishop_grandin = car("Abinojii Mikanah")  # its name on the map since 2022

    response = await call(
        api, "/internal/pickup-points", pickups_request(api), foot(), car=on_bishop_grandin
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"pickups": []}


async def test_unnamed_roads_get_the_default_label(api: API) -> None:
    body = pickups_request(api, limit=1)

    response = await call(api, "/internal/pickup-points", body, foot(), car=car(""))

    assert response.json()["pickups"][0]["label"] == DEFAULT_PICKUP_LABEL


async def test_a_rider_who_cant_walk_to_the_route_gets_no_points(api: API) -> None:
    """Across the river: inside the corridor, but a long walk round to a bridge."""
    response = await call(api, "/internal/pickup-points", pickups_request(api), foot(detour=5))

    assert response.status_code == 200, response.text
    assert response.json() == {"pickups": []}


async def test_unknown_trip_returns_404_without_calling_osrm(api: API) -> None:
    body = pickups_request(api, tripId=str(uuid4()))

    response = await call(api, "/internal/pickup-points", body, foot())

    assert response.status_code == 404
    assert response.json()["code"] == "route_not_found"
    assert api.osrm_requests == []


async def test_walking_engine_down_returns_503(api: API) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OSRM is not running", request=request)

    response = await call(api, "/internal/pickup-points", pickups_request(api), down)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_engine_unavailable"


@pytest.mark.parametrize(
    "change",
    [
        {"limit": 0},
        {"limit": 6},
        {"rider": {"lat": 91, "lng": 0}},
        {"tripId": "not-a-uuid"},
        {"rider": None},
    ],
)
async def test_invalid_input_returns_422_without_calling_osrm(
    api: API, change: dict[str, Any]
) -> None:
    body = pickups_request(api, **change)

    response = await call(api, "/internal/pickup-points", body, foot())

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert api.osrm_requests == []
