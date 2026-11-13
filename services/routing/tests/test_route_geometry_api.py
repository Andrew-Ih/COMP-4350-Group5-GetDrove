"""GET /trips/{trip_id}/geometry with a real PostgreSQL database (#123, #135)."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.domain.corridor import distance_meters, sample_route
from routing.domain.entities import Route
from routing.domain.pickups import PRIVATE_END_METERS
from routing.domain.values import Direction, LatLng
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("routing_database")

# Osborne Village to campus: the start is the driver's own end going to campus.
ROUTE_PATH = (
    LatLng(lat=49.876812, lng=-97.143807),
    LatLng(lat=49.8421, lng=-97.1502),
    LatLng(lat=49.8075, lng=-97.1366),
)
START, END = ROUTE_PATH[0], ROUTE_PATH[-1]


class API:
    def __init__(self, app: FastAPI, auth: TestAuth, engine: AsyncEngine) -> None:
        self.app, self.auth, self.engine = app, auth, engine
        self.trip_ids: list[UUID] = []

    async def add(self, driver_id: UUID | None, direction: Direction | None) -> Route:
        route = Route(
            trip_id=uuid4(),
            path=ROUTE_PATH,
            distance_meters=8832,
            duration_seconds=793,
            driver_id=driver_id,
            direction=direction,
        )
        async with self.app.state.session_factory() as session, session.begin():
            await SQLAlchemyRouteRepository(session).save(route, sample_route(route))
        self.trip_ids.append(route.trip_id)
        return route

    async def get(self, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url="http://test",
            headers=self.auth.headers() if headers is None else headers,
        ) as client:
            return await client.get(path)

    def as_someone_else(self) -> dict[str, str]:
        return self.auth.headers(user_id=uuid4())


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    api = API(app, auth, engine)
    try:
        yield api
    finally:
        # Each test has its own trip IDs. Clean up even when an assertion fails.
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(routes).where(routes.c.trip_id.in_(api.trip_ids)))
        finally:
            await engine.dispose()


def line(response: httpx.Response) -> list[LatLng]:
    assert response.status_code == 200, response.text
    return [LatLng(lat=lat, lng=lng) for lng, lat in response.json()["geometry"]["coordinates"]]


def closest_to(point: LatLng, points: list[LatLng]) -> float:
    return min(distance_meters(point, p) for p in points)


async def test_the_driver_gets_the_whole_route_as_a_geojson_feature(api: API) -> None:
    route = await api.add(driver_id=api.auth.user_id, direction=Direction.TO_CAMPUS)

    response = await api.get(f"/trips/{route.trip_id}/geometry")

    assert response.status_code == 200, response.text
    # Exactly what MapLibre draws: coordinates in GeoJSON's [lng, lat] order.
    assert response.json() == {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[-97.143807, 49.876812], [-97.1502, 49.8421], [-97.1366, 49.8075]],
        },
        "properties": {
            "tripId": str(route.trip_id),
            "distanceMeters": 8832,
            "durationSeconds": 793,
        },
    }


async def test_going_to_campus_riders_never_see_the_drivers_start(api: API) -> None:
    route = await api.add(driver_id=uuid4(), direction=Direction.TO_CAMPUS)

    seen = line(await api.get(f"/trips/{route.trip_id}/geometry", headers=api.as_someone_else()))

    # Nothing within the margin of where the driver starts; the cut is right at the margin.
    assert closest_to(START, seen) >= PRIVATE_END_METERS - 1
    assert distance_meters(START, seen[0]) == pytest.approx(PRIVATE_END_METERS, abs=1)
    # The campus end is still drawn, so the map shows where the trip goes.
    assert seen[-1] == END


async def test_leaving_campus_riders_never_see_where_the_driver_ends(api: API) -> None:
    route = await api.add(driver_id=uuid4(), direction=Direction.FROM_CAMPUS)

    seen = line(await api.get(f"/trips/{route.trip_id}/geometry", headers=api.as_someone_else()))

    assert closest_to(END, seen) >= PRIVATE_END_METERS - 1
    assert seen[0] == START


async def test_routes_stored_before_sprint_2_hide_both_ends_from_everyone(api: API) -> None:
    """No driver or direction stored: nobody is the driver, and either end could be home."""
    route = await api.add(driver_id=None, direction=None)

    seen = line(await api.get(f"/trips/{route.trip_id}/geometry"))

    assert closest_to(START, seen) >= PRIVATE_END_METERS - 1
    assert closest_to(END, seen) >= PRIVATE_END_METERS - 1


async def test_properties_are_the_whole_trips(api: API) -> None:
    """The distance and duration are the trip's, as shown on the trip itself, not the
    trimmed line's."""
    route = await api.add(driver_id=uuid4(), direction=Direction.TO_CAMPUS)

    response = await api.get(f"/trips/{route.trip_id}/geometry", headers=api.as_someone_else())

    assert response.json()["properties"] == {
        "tripId": str(route.trip_id),
        "distanceMeters": 8832,
        "durationSeconds": 793,
    }


async def test_unknown_trip_returns_404(api: API) -> None:
    response = await api.get(f"/trips/{uuid4()}/geometry")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "route_not_found"


@pytest.mark.parametrize(
    "case,code",
    [("missing", "unauthorized"), ("garbage", "invalid_token"), ("expired", "token_expired")],
)
async def test_requires_a_valid_login(api: API, case: str, code: str) -> None:
    route = await api.add(driver_id=api.auth.user_id, direction=Direction.TO_CAMPUS)
    headers = {
        "missing": {},
        "garbage": {"Authorization": "Bearer not-a-token"},
        "expired": api.auth.headers(expires_in=-60),
    }[case]

    response = await api.get(f"/trips/{route.trip_id}/geometry", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == code


async def test_invalid_trip_id_returns_422(api: API) -> None:
    response = await api.get("/trips/not-a-uuid/geometry")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
