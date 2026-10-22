"""Integration tests for GET /trips/mine using real PostgreSQL transactions."""

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.tables import outbox, trips
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type API = tuple[FastAPI, TestAuth, AsyncEngine]
type Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield app, auth, engine
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    delete(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(auth.user_id)
                    )
                )
                await connection.execute(delete(trips).where(trips.c.driver_id == auth.user_id))
        finally:
            await engine.dispose()


def payload(departure_at: datetime) -> dict[str, Any]:
    return {
        "direction": "to_campus",
        "place": {"label": "Pembina Highway", "lat": 49.82, "lng": -97.15},
        "departureAt": departure_at.isoformat(),
        "seatsTotal": 3,
    }


def route(request: httpx.Request) -> httpx.Response:
    """Mock the routing service used when creating test trips."""
    assert request.method == "POST"
    assert request.url.path == "/internal/routes"
    data = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "tripId": data["tripId"],
            "distanceMeters": 6000,
            "durationSeconds": 900,
        },
    )


async def post_trip(api: API, body: dict[str, Any]) -> httpx.Response:
    app, auth, _ = api

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(route),
        base_url="http://routing:8000",
    ) as routing_client:
        app.state.routing_client = routing_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
        ) as client:
            return await client.post("/", json=body)


async def get_my_trips(api: API) -> httpx.Response:
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
    ) as client:
        return await client.get("/mine")


@pytest.mark.asyncio
async def test_my_trips_returns_trips_in_departure_order(api: API) -> None:
    now = datetime.now(UTC)

    # Create the later trip first to verify that the endpoint sorts the results.
    later = await post_trip(api, payload(now + timedelta(days=3)))
    earlier = await post_trip(api, payload(now + timedelta(days=2)))

    assert later.status_code == 201, later.text
    assert earlier.status_code == 201, earlier.text

    response = await get_my_trips(api)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2

    departure_times = [datetime.fromisoformat(trip["departureAt"]) for trip in body]
    assert departure_times == sorted(departure_times)
    assert all(trip["driverId"] == str(api[1].user_id) for trip in body)

    assert "seatsAvailable" in body[0]
    assert "departureAt" in body[0]


@pytest.mark.asyncio
async def test_my_trips_returns_empty_list_when_driver_has_no_trips(
    api: API,
) -> None:
    response = await get_my_trips(api)

    assert response.status_code == 200, response.text
    assert response.json() == []
