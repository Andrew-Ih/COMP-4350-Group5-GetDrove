"""POST /trips with real PostgreSQL transactions and a mocked Routing boundary."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, event, select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

from common_security.testing import TestAuth
from events.outbox import OutboxRelay
from trips.adapters.events import OutboxTripEvents
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox, trips
from trips.domain.entities import Trip
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
        # Each test has its own driver ID. Clean up even when an assertion fails.
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


def payload() -> dict[str, Any]:
    return {
        "direction": "to_campus",
        "place": {"label": "Pembina Highway", "lat": 49.82, "lng": -97.15},
        "departureAt": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "seatsTotal": 3,
    }


def route(request: httpx.Request) -> httpx.Response:
    assert request.method == "POST"
    assert request.url.path == "/internal/routes"
    data = json.loads(request.content)
    assert (data["origin"]["lat"], data["destination"]["lat"]) in {
        (49.82, 49.8075),
        (49.8075, 49.82),
    }
    return httpx.Response(
        200,
        json={
            "tripId": data["tripId"],
            "distanceMeters": 6000,
            "durationSeconds": 900,
        },
    )


async def post(api: API, handler: Handler, body: dict[str, Any]) -> httpx.Response:
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as routing_client:
        app.state.routing_client = routing_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
        ) as client:
            return await client.post("/", json=body)


async def saved(api: API) -> list[RowMapping]:
    _, auth, engine = api
    # A separate connection proves committed visibility, not just a pending INSERT.
    async with engine.connect() as connection:
        return list(
            (
                await connection.execute(select(trips).where(trips.c.driver_id == auth.user_id))
            ).mappings()
        )


async def saved_events(api: API) -> list[RowMapping]:
    async with api[2].connect() as connection:
        return list(
            (
                await connection.execute(
                    select(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(api[1].user_id)
                    )
                )
            ).mappings()
        )


@pytest.mark.parametrize("direction", ["to_campus", "from_campus"])
async def test_post_trip_returns_201_and_commits_trip(api: API, direction: str) -> None:
    body_in = {**payload(), "direction": direction}
    response = await post(api, route, body_in)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["driverId"] == str(api[1].user_id)
    assert body["distanceMeters"] == 6000
    assert body["durationSeconds"] == 900
    assert body["seatsAvailable"] == 3
    assert body["status"] == "scheduled"
    private_end = "origin" if direction == "to_campus" else "destination"
    assert body[private_end] == body_in["place"]
    assert datetime.fromisoformat(body["estimatedArrivalAt"]) == (
        datetime.fromisoformat(body_in["departureAt"]) + timedelta(seconds=900)
    )
    rows = await saved(api)
    assert len(rows) == 1
    assert str(rows[0]["id"]) == body["id"]
    assert rows[0]["driver_id"] == api[1].user_id
    events = await saved_events(api)
    assert len(events) == 1
    assert events[0]["type"] == "TripPosted"
    assert events[0]["envelope"]["version"] == 1
    assert events[0]["envelope"]["producer"] == "trips"
    assert events[0]["envelope"]["payload"] == {"tripId": body["id"]}
    assert events[0]["published_at"] is None


@pytest.mark.parametrize(
    "change,code",
    [
        (
            {"departureAt": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
            "departure_in_past",
        ),
        ({"departureAt": "2026-10-20T13:10:00"}, "invalid_input"),
        ({"seatsTotal": 0}, "invalid_input"),
        ({"seatsTotal": 7}, "invalid_input"),
    ],
)
async def test_invalid_input_saves_nothing(api: API, change: dict[str, Any], code: str) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("Routing must not be called for invalid input")

    response = await post(api, unexpected, {**payload(), **change})
    assert response.status_code == 422
    assert response.json()["code"] == code
    assert await saved(api) == []
    assert await saved_events(api) == []


async def test_routing_failure_returns_503_and_saves_nothing(
    api: API, routing_failure: Handler
) -> None:
    response = await post(api, routing_failure, payload())
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_unavailable"
    assert await saved(api) == []
    assert await saved_events(api) == []


@pytest.mark.parametrize("stage", ["after-insert", "database", "outbox", "commit"])
async def test_database_failure_rolls_back_trip(
    api: API, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    inserted = False
    original_add = SQLAlchemyTripRepository.add

    async def add(self: SQLAlchemyTripRepository, trip: Trip) -> None:
        nonlocal inserted
        await original_add(self, trip)
        inserted = True
        if stage == "database":
            await self.session.execute(text("SELECT 1 / 0"))
        if stage == "after-insert":
            raise OperationalError("insert", {}, RuntimeError("database failure"))

    monkeypatch.setattr(SQLAlchemyTripRepository, "add", add)
    if stage == "outbox":
        original_publish = OutboxTripEvents.trip_posted

        async def fail_outbox(self: OutboxTripEvents, trip_id: UUID) -> None:
            await original_publish(self, trip_id)
            raise OperationalError("outbox", {}, RuntimeError("database failure"))

        monkeypatch.setattr(OutboxTripEvents, "trip_posted", fail_outbox)
    if stage == "commit":

        class FailingSession(AsyncSession):
            pass

        def fail_commit(session: Session) -> None:
            raise OperationalError("commit", {}, RuntimeError("database failure"))

        factory = async_sessionmaker(api[2], class_=FailingSession)

        # Attach only to this test's session, leaving cleanup and other tests intact.
        def session_factory() -> FailingSession:
            session = factory()
            event.listen(session.sync_session, "before_commit", fail_commit)
            return session

        api[0].state.session_factory = session_factory

    response = await post(api, route, payload())
    assert inserted
    assert response.status_code == 500
    assert await saved(api) == []
    assert await saved_events(api) == []


async def test_lifespan_retries_pending_event_and_stops_relay(
    api: API, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await post(api, route, payload())
    assert response.status_code == 201
    redis = AsyncMock(spec=Redis)
    delivered = asyncio.Event()
    attempts = 0

    async def xadd(stream: str, fields: dict[str, str]) -> bytes:
        nonlocal attempts
        attempts += 1
        assert stream == "events.trips"
        assert fields["type"] == "TripPosted"
        assert json.loads(fields["envelope"])["payload"] == {"tripId": response.json()["id"]}
        if attempts == 1:
            raise RedisConnectionError("Redis temporarily unavailable")
        return b"1-0"

    original_publish = OutboxRelay.publish_pending

    async def publish_pending(self: OutboxRelay) -> int:
        count = await original_publish(self)
        if count:
            delivered.set()
        return count

    monkeypatch.setattr(OutboxRelay, "publish_pending", publish_pending)
    redis.xadd.side_effect = xadd
    monkeypatch.setattr("trips.infrastructure.main.Redis.from_url", lambda url: redis)
    app = api[0]
    async with app.router.lifespan_context(app), asyncio.timeout(5):
        await delivered.wait()
        assert (await saved_events(api))[0]["published_at"] is not None

    assert attempts == 2
    redis.aclose.assert_awaited_once()


async def test_invalid_routing_location_returns_422_and_saves_nothing(
    api: API,
) -> None:
    """An unroutable location should return 422 without saving anything."""

    def invalid_location(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"code": "invalid_input"},
        )

    response = await post(api, invalid_location, payload())

    assert response.status_code == 422, response.text

    body = response.json()
    assert body["code"] == "invalid_input"
    assert body["errors"] == [
        {
            "field": "place",
            "message": "We couldn't find a driving route from this place.",
        }
    ]

    assert await saved(api) == []
    assert await saved_events(api) == []


async def test_past_departure_identifies_invalid_field(api: API) -> None:
    """A past departure should identify departureAt in the error response."""

    body = {
        **payload(),
        "departureAt": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    }

    response = await post(api, route, body)

    assert response.status_code == 422, response.text

    result = response.json()
    assert result["code"] == "departure_in_past"
    assert result["errors"] == [
        {
            "field": "departureAt",
            "message": "Must be in the future",
        }
    ]

    assert await saved(api) == []
    assert await saved_events(api) == []
