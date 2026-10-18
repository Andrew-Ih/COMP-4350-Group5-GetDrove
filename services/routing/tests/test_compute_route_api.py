"""POST /internal/routes with real PostgreSQL transactions and a mocked OSRM (#24)."""

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from routing.adapters.persistence.tables import routes
from routing.infrastructure.main import create_app
from routing.infrastructure.settings import get_settings

type API = tuple[FastAPI, AsyncEngine, UUID]
type Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
async def api() -> AsyncIterator[API]:
    app = create_app()
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    trip_id = uuid4()
    try:
        yield app, engine, trip_id
    finally:
        # Each test has its own trip ID. Clean up even when an assertion fails.
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(routes).where(routes.c.trip_id == trip_id))
        finally:
            await engine.dispose()


def payload(trip_id: UUID) -> dict[str, Any]:
    return {
        "tripId": str(trip_id),
        "origin": {"lat": 49.82, "lng": -97.15},
        "destination": {"lat": 49.8075, "lng": -97.1366},
    }


async def post(api: API, handler: Handler, body: dict[str, Any]) -> httpx.Response:
    app = api[0]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-car:5000"
    ) as osrm_client:
        app.state.osrm_car_client = osrm_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.post("/internal/routes", json=body)


async def saved(api: API) -> list[RowMapping]:
    _, engine, trip_id = api
    # A separate connection proves committed visibility, not just a pending INSERT.
    async with engine.connect() as connection:
        result = await connection.execute(
            select(
                routes.c.distance_meters,
                routes.c.duration_seconds,
                func.ST_NPoints(routes.c.path).label("points"),
            ).where(routes.c.trip_id == trip_id)
        )
        return list(result.mappings())


async def test_compute_route_returns_metrics_and_commits_route(
    api: API, osrm_route: Handler
) -> None:
    response = await post(api, osrm_route, payload(api[2]))

    assert response.status_code == 200, response.text
    assert response.json() == {
        "tripId": str(api[2]),
        "distanceMeters": 6000,
        "durationSeconds": 900,
    }
    rows = await saved(api)
    assert len(rows) == 1
    assert rows[0]["points"] == 3
    assert rows[0]["distance_meters"] == 6000
    assert rows[0]["duration_seconds"] == 900


async def test_computing_again_replaces_the_route(api: API, osrm_route: Handler) -> None:
    def longer(request: httpx.Request) -> httpx.Response:
        body = osrm_route(request).json()
        body["routes"][0]["distance"] = 7200
        return httpx.Response(200, json=body)

    assert (await post(api, osrm_route, payload(api[2]))).status_code == 200
    response = await post(api, longer, payload(api[2]))

    assert response.status_code == 200, response.text
    assert response.json()["distanceMeters"] == 7200
    rows = await saved(api)
    assert len(rows) == 1
    assert rows[0]["distance_meters"] == 7200


async def test_no_route_returns_422_and_saves_nothing(api: API, osrm_no_route: Handler) -> None:
    response = await post(api, osrm_no_route, payload(api[2]))

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_input"
    assert [error["field"] for error in body["errors"]] == ["origin", "destination"]
    assert await saved(api) == []


async def test_engine_failure_returns_503_and_saves_nothing(
    api: API, osrm_failure: Handler
) -> None:
    response = await post(api, osrm_failure, payload(api[2]))

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_engine_unavailable"
    assert await saved(api) == []


@pytest.mark.parametrize(
    "change",
    [
        {"tripId": "not-a-uuid"},
        {"origin": {"lat": 120, "lng": -97.15}},
        {"destination": {"lat": 49.8075, "lng": -200}},
        {"origin": None},
    ],
)
async def test_invalid_input_never_calls_osrm(api: API, change: dict[str, Any]) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("OSRM must not be called for invalid input")

    response = await post(api, unexpected, {**payload(api[2]), **change})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert await saved(api) == []
