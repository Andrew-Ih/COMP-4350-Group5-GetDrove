"""Integration tests for POST /series with PostgreSQL and mocked routing."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox, trip_series, trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, TripStatus
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")
WINNIPEG = ZoneInfo("America/Winnipeg")


@pytest.fixture
async def api() -> AsyncIterator[tuple[Any, TestAuth, Any]]:
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
                await connection.execute(
                    delete(trip_series).where(trip_series.c.driver_id == auth.user_id)
                )
        finally:
            await engine.dispose()


def series_payload() -> dict[str, Any]:
    """Pick the next Monday using Winnipeg local time."""
    now = datetime.now(WINNIPEG)
    days_until_monday = (0 - now.weekday()) % 7

    if days_until_monday == 0:
        days_until_monday = 7

    first_date = now.date() + timedelta(days=days_until_monday)

    first_local = datetime.combine(
        first_date,
        datetime.min.time().replace(hour=8),
        WINNIPEG,
    )

    return {
        "direction": "to_campus",
        "place": {
            "label": "Pembina Highway",
            "lat": 49.82,
            "lng": -97.15,
        },
        "departureAt": first_local.astimezone(UTC).isoformat(),
        "seatsTotal": 3,
        "weekdays": ["mon", "wed", "fri"],
        "endDate": (first_date + timedelta(days=6)).isoformat(),
    }


def route(request: httpx.Request) -> httpx.Response:
    """Mock the routing service."""
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


async def saved_rows(
    engine: Any,
    driver_id: Any,
) -> tuple[list[Any], list[Any], list[Any]]:
    """Read committed database rows using a separate connection."""
    async with engine.connect() as connection:
        saved_series = (
            (
                await connection.execute(
                    select(trip_series).where(trip_series.c.driver_id == driver_id)
                )
            )
            .mappings()
            .all()
        )

        saved_trips = (
            (await connection.execute(select(trips).where(trips.c.driver_id == driver_id)))
            .mappings()
            .all()
        )

        saved_events = (
            (
                await connection.execute(
                    select(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(driver_id)
                    )
                )
            )
            .mappings()
            .all()
        )

    return saved_series, saved_trips, saved_events


async def test_post_series_creates_searchable_trips_and_events(
    api: tuple[Any, TestAuth, Any],
) -> None:
    app, auth, engine = api
    routed_ids: set[str] = set()

    def routing(request: httpx.Request) -> httpx.Response:
        data = json.loads(request.content)
        if request.url.path == "/internal/routes":
            assert data["driverId"] == str(auth.user_id)
            assert data["direction"] == "to_campus"
            routed_ids.add(data["tripId"])
            return route(request)
        assert request.url.path == "/internal/matches"
        return httpx.Response(
            200,
            json={
                "matches": [
                    {
                        "tripId": trip_id,
                        "pickup": {"label": "Pembina Highway", "lat": 49.82, "lng": -97.15},
                        "walkSeconds": 60,
                        "riderDistanceMeters": 4000,
                    }
                    for trip_id in data["tripIds"]
                    if trip_id in routed_ids
                ],
            },
        )

    body = series_payload()

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(routing),
            base_url="http://routing:8000",
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(503)),
            base_url="http://payments:8000",
        ) as payments_client,
    ):
        app.state.routing_client = routing_client
        app.state.payments_client = payments_client

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=app,
                raise_app_exceptions=False,
            ),
            base_url="http://test",
            headers={
                **auth.headers(),
                "X-Request-ID": str(auth.user_id),
            },
        ) as client:
            response = await client.post("/series", json=body)
            assert response.status_code == 201, response.text
            occurrence = response.json()["trips"][0]
            search = await client.get(
                "/search",
                params={
                    "lat": 49.82,
                    "lng": -97.15,
                    "direction": "to_campus",
                    "time": occurrence["estimatedArrivalAt"],
                },
                headers=auth.headers(user_id=uuid4()),
            )

    assert search.status_code == 200, search.text
    assert [result["trip"]["id"] for result in search.json()] == [occurrence["id"]]

    result = response.json()

    assert len(result["trips"]) == 3
    assert result["skippedDates"] == []
    assert routed_ids == {trip["id"] for trip in result["trips"]}

    series_id = result["seriesId"]

    assert all(trip["seriesId"] == series_id for trip in result["trips"])

    assert all(trip["driverId"] == str(auth.user_id) for trip in result["trips"])

    assert all(trip["durationSeconds"] == 900 for trip in result["trips"])

    assert all(trip["status"] == "scheduled" for trip in result["trips"])

    local_departures = [
        datetime.fromisoformat(trip["departureAt"]).astimezone(WINNIPEG) for trip in result["trips"]
    ]

    assert [departure.weekday() for departure in local_departures] == [0, 2, 4]

    assert all((departure.hour, departure.minute) == (8, 0) for departure in local_departures)

    saved_series, saved_trips, saved_events = await saved_rows(engine, auth.user_id)

    assert len(saved_series) == 1
    assert str(saved_series[0]["id"]) == series_id

    assert len(saved_trips) == 3

    assert {str(row["id"]) for row in saved_trips} == {trip["id"] for trip in result["trips"]}

    assert all(str(row["series_id"]) == series_id for row in saved_trips)

    assert len(saved_events) == 3

    assert all(row["type"] == "TripPosted" for row in saved_events)

    assert {row["envelope"]["payload"]["tripId"] for row in saved_events} == {
        trip["id"] for trip in result["trips"]
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
    ) as client:
        cancelled = await client.post(f"/{occurrence['id']}/cancel")

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["seriesId"] == series_id
    _, saved_trips, saved_events = await saved_rows(engine, auth.user_id)
    assert {str(row["id"]): row["status"] for row in saved_trips} == {
        trip["id"]: "cancelled" if trip["id"] == occurrence["id"] else "scheduled"
        for trip in result["trips"]
    }
    [event] = [row["envelope"] for row in saved_events if row["type"] == "TripCancelled"]
    assert event["payload"]["tripId"] == occurrence["id"]
    assert event["payload"]["seriesId"] == series_id


async def test_concurrent_series_do_not_duplicate_trips(
    api: tuple[Any, TestAuth, Any],
) -> None:
    """Two simultaneous requests must not create overlapping trips."""
    app, auth, engine = api

    body = series_payload()
    routing_calls = 0

    def counting_route(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal routing_calls
        routing_calls += 1
        return route(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(counting_route),
        base_url="http://routing:8000",
    ) as routing_client:
        app.state.routing_client = routing_client

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=app,
                raise_app_exceptions=False,
            ),
            base_url="http://test",
            headers={
                **auth.headers(),
                "X-Request-ID": str(auth.user_id),
            },
        ) as client:
            responses = await asyncio.wait_for(
                asyncio.gather(
                    client.post("/series", json=body),
                    client.post("/series", json=body),
                ),
                timeout=15,
            )

    assert all(response.status_code == 201 for response in responses), [
        (response.status_code, response.text) for response in responses
    ]

    results = [response.json() for response in responses]

    # Both series should exist, but only three trips total.
    assert sorted(len(result["trips"]) for result in results) == [0, 3]

    assert sorted(len(result["skippedDates"]) for result in results) == [0, 3]

    assert routing_calls == 6

    series_ids = {result["seriesId"] for result in results}

    assert len(series_ids) == 2

    saved_series, saved_trips, saved_events = await saved_rows(engine, auth.user_id)

    # Both recurring series are persisted.
    assert len(saved_series) == 2

    assert {str(row["id"]) for row in saved_series} == series_ids

    # The advisory lock prevents duplicate trip generation.
    assert len(saved_trips) == 3

    departures = [row["departure_at"] for row in saved_trips]

    assert len(set(departures)) == 3

    # Every generated trip belongs to one of the two series.
    assert all(str(row["series_id"]) in series_ids for row in saved_trips)

    # Only the three actual trips produce events.
    assert len(saved_events) == 3

    assert all(row["type"] == "TripPosted" for row in saved_events)

    assert {row["envelope"]["payload"]["tripId"] for row in saved_events} == {
        str(row["id"]) for row in saved_trips
    }


async def test_in_progress_trip_blocks_overlapping_occurrence(
    api: tuple[Any, TestAuth, Any],
) -> None:
    app, auth, _ = api
    body = series_payload()
    first = datetime.fromisoformat(body["departureAt"])
    started_at = datetime.now(UTC) - timedelta(minutes=1)
    existing = Trip.create(
        driver_id=auth.user_id,
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=started_at,
        duration_seconds=int((first - started_at).total_seconds()) + 900,
        distance_meters=6000,
        seats_total=3,
    )
    existing.status = TripStatus.IN_PROGRESS
    async with app.state.session_factory.begin() as session:
        await SQLAlchemyTripRepository(session).add(existing)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(route), base_url="http://routing:8000"
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
        ) as client,
    ):
        app.state.routing_client = routing_client
        response = await client.post("/series", json=body)

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["skippedDates"] == [first.astimezone(WINNIPEG).date().isoformat()]
    assert len(result["trips"]) == 2


async def test_recurring_lock_uses_a_separate_namespace_from_seat_requests(
    api: tuple[Any, TestAuth, Any],
) -> None:
    app, auth, _ = api
    sessions = app.state.session_factory
    try_lock = text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))")

    async with sessions.begin() as recurring, sessions.begin() as other:
        await SQLAlchemyTripRepository(recurring).lock_driver(auth.user_id)
        assert await other.scalar(try_lock, {"key": f"trips.driver-trips:{auth.user_id}"}) is False
        assert await other.scalar(try_lock, {"key": f"trips.seat-requests:{auth.user_id}"}) is True


async def test_post_series_rolls_back_when_routing_fails(
    api: tuple[Any, TestAuth, Any],
) -> None:
    """A routing failure must not persist a partial series."""
    app, auth, engine = api
    routing_calls = 0
    sibling_started = asyncio.Event()
    sibling_stopped = asyncio.Event()

    async def failing_route(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal routing_calls
        routing_calls += 1
        if routing_calls == 1:
            return route(request)
        if routing_calls == 3:
            sibling_started.set()
            try:
                await asyncio.Future()
            finally:
                sibling_stopped.set()
        await sibling_started.wait()
        assert request.url.path == "/internal/routes"
        return httpx.Response(
            503,
            json={"detail": "Routing service unavailable"},
        )

    body = series_payload()

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(failing_route),
        base_url="http://routing:8000",
    ) as routing_client:
        app.state.routing_client = routing_client

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=app,
                raise_app_exceptions=False,
            ),
            base_url="http://test",
            headers={
                **auth.headers(),
                "X-Request-ID": str(auth.user_id),
            },
        ) as client:
            async with asyncio.timeout(5):
                response = await client.post("/series", json=body)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_unavailable"
    assert routing_calls == 3
    assert sibling_stopped.is_set()

    saved_series, saved_trips, saved_events = await saved_rows(engine, auth.user_id)

    assert saved_series == []
    assert saved_trips == []
    assert saved_events == []
