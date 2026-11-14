"""Integration tests for POST /series with PostgreSQL and mocked routing."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.tables import outbox, trip_series, trips
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


async def test_post_series_creates_trips_and_events(
    api: tuple[Any, TestAuth, Any],
) -> None:
    app, auth, engine = api
    routing_calls = 0

    def counting_route(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal routing_calls
        routing_calls += 1
        return route(request)

    body = series_payload()

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
            response = await client.post("/series", json=body)

    assert response.status_code == 201, response.text

    result = response.json()

    assert len(result["trips"]) == 3
    assert result["skippedDates"] == []
    assert routing_calls == 1

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

    assert routing_calls == 2

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


async def test_post_series_rolls_back_when_routing_fails(
    api: tuple[Any, TestAuth, Any],
) -> None:
    """A routing failure must not persist a partial series."""
    app, auth, engine = api

    def failing_route(
        request: httpx.Request,
    ) -> httpx.Response:
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
            response = await client.post("/series", json=body)

    assert response.status_code >= 500, response.text

    saved_series, saved_trips, saved_events = await saved_rows(engine, auth.user_id)

    assert saved_series == []
    assert saved_trips == []
    assert saved_events == []
