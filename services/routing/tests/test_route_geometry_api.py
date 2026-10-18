"""GET /trips/{trip_id}/geometry with a real PostgreSQL database (#123)."""

from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from routing.adapters.persistence.repository import SQLAlchemyRouteRepository
from routing.adapters.persistence.tables import routes
from routing.domain.corridor import sample_route
from routing.domain.entities import Route
from routing.domain.values import LatLng
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

type API = tuple[FastAPI, TestAuth, AsyncEngine, Route]

ROUTE_PATH = (
    LatLng(lat=49.876812, lng=-97.143807),
    LatLng(lat=49.8421, lng=-97.1502),
    LatLng(lat=49.8075, lng=-97.1366),
)


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    route = Route(trip_id=uuid4(), path=ROUTE_PATH, distance_meters=8832, duration_seconds=793)
    try:
        async with app.state.session_factory() as session, session.begin():
            await SQLAlchemyRouteRepository(session).save(route, sample_route(route))
        yield app, auth, engine, route
    finally:
        # Each test has its own trip ID. Clean up even when an assertion fails.
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(routes).where(routes.c.trip_id == route.trip_id))
        finally:
            await engine.dispose()


async def get(api: API, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    app, auth, _, _ = api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers=auth.headers() if headers is None else headers,
    ) as client:
        return await client.get(path)


async def test_returns_the_route_as_a_geojson_feature(api: API) -> None:
    route = api[3]

    response = await get(api, f"/trips/{route.trip_id}/geometry")

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


async def test_any_logged_in_user_gets_the_full_route(api: API) -> None:
    """Sprint 1: not just the driver. Riders get a trimmed route from Sprint 2."""
    route, other_user = api[3], api[1].headers(user_id=uuid4())

    response = await get(api, f"/trips/{route.trip_id}/geometry", headers=other_user)

    assert response.status_code == 200
    assert len(response.json()["geometry"]["coordinates"]) == len(ROUTE_PATH)


async def test_unknown_trip_returns_404(api: API) -> None:
    response = await get(api, f"/trips/{uuid4()}/geometry")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "route_not_found"


@pytest.mark.parametrize(
    "case,code",
    [("missing", "unauthorized"), ("garbage", "invalid_token"), ("expired", "token_expired")],
)
async def test_requires_a_valid_login(api: API, case: str, code: str) -> None:
    headers = {
        "missing": {},
        "garbage": {"Authorization": "Bearer not-a-token"},
        "expired": api[1].headers(expires_in=-60),
    }[case]

    response = await get(api, f"/trips/{api[3].trip_id}/geometry", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == code


async def test_invalid_trip_id_returns_422(api: API) -> None:
    response = await get(api, "/trips/not-a-uuid/geometry")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
