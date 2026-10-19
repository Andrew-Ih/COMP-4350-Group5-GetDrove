"""GET /search with real PostgreSQL and mocked Routing and Payments (#97)."""

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

type Handler = Callable[[httpx.Request], httpx.Response]

# Well in the future, so other trips in a local database don't get in the way.
TIME = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
RIDER = {"lat": 49.85, "lng": -97.15}
# The driver's own end of the trip: never shown to riders.
HOME = Location("Driver's home street", 49.82, -97.15)


def trip(minutes_before: int, direction: Direction = Direction.TO_CAMPUS) -> Trip:
    """A trip arriving (to campus) or leaving (from campus) around TIME."""
    offset = timedelta(minutes=minutes_before)
    departure = TIME - offset if direction == Direction.TO_CAMPUS else TIME + offset
    return Trip.create(
        driver_id=uuid4(),
        direction=direction,
        place=HOME,
        departure_at=departure,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )


class API:
    def __init__(self, app: FastAPI, auth: TestAuth, engine: AsyncEngine) -> None:
        self.app, self.auth, self.engine = app, auth, engine
        self.added: list[Trip] = []
        self.routing_requests: list[httpx.Request] = []

    async def add(self, *new: Trip) -> None:
        async with self.app.state.session_factory() as session, session.begin():
            for t in new:
                await SQLAlchemyTripRepository(session).add(t)
        self.added.extend(new)


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
        # Clean up even when an assertion fails.
        try:
            async with engine.begin() as connection:
                ids = [t.id for t in api.added]
                await connection.execute(delete(trips).where(trips.c.id.in_(ids)))
        finally:
            await engine.dispose()


def routing(*matched: Trip, walk: int = 240, to_end: int = 4000) -> Handler:
    """Routing's /internal/matches: these trips match, if they were candidates."""

    def handler(request: httpx.Request) -> httpx.Response:
        asked = set(json.loads(request.content)["tripIds"])
        return httpx.Response(
            200,
            json={
                "matches": [
                    {
                        "tripId": str(t.id),
                        "pickup": {"label": "Pembina Highway", "lat": 49.84, "lng": -97.15},
                        "walkSeconds": walk,
                        # Routing's field: the rest of the route from the pickup.
                        "riderDistanceMeters": to_end,
                    }
                    for t in matched
                    if str(t.id) in asked
                ]
            },
        )

    return handler


def payments(request: httpx.Request) -> httpx.Response:
    distance = json.loads(request.content)["distanceMeters"]
    return httpx.Response(
        200,
        json={
            "amountCents": max(200, round(distance * 0.045 / 5) * 5),
            "currency": "CAD",
            "explanation": f"{distance / 1000:.1f} km at $0.45/km",
        },
    )


async def search(
    api: API,
    routing: Handler,
    payments: Handler = payments,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    def recording(request: httpx.Request) -> httpx.Response:
        api.routing_requests.append(request)
        return routing(request)

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(recording), base_url="http://routing:8000"
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(payments), base_url="http://payments:8000"
        ) as payments_client,
    ):
        api.app.state.routing_client = routing_client
        api.app.state.payments_client = payments_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app, raise_app_exceptions=False),
            base_url="http://test",
            headers=api.auth.headers() if headers is None else headers,
        ) as client:
            query = params or {**RIDER, "direction": "to_campus", "time": TIME.isoformat()}
            return await client.get("/search", params=query)


async def test_returns_matching_trips_with_pickup_and_cost(api: API) -> None:
    match = trip(minutes_before=40)
    await api.add(match)

    response = await search(api, routing(match))

    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["trip"]["id"] == str(match.id)
    assert result["trip"]["seatsAvailable"] == 3
    assert result["pickup"] == {
        "label": "Pembina Highway",
        "lat": 49.84,
        "lng": -97.15,
        "walkSeconds": 240,
    }
    # 4 km at $0.45/km is $1.80, under Payments' $2.00 minimum.
    assert result["cost"] == {
        "amountCents": 200,
        "currency": "CAD",
        "explanation": "4.0 km at $0.45/km",
    }
    # Routing was asked about the candidate, with the rider's location.
    [request] = api.routing_requests
    body = json.loads(request.content)
    assert body["rider"] == RIDER
    assert str(match.id) in body["tripIds"]


@pytest.mark.parametrize("direction", [Direction.TO_CAMPUS, Direction.FROM_CAMPUS])
async def test_the_drivers_end_of_the_trip_is_private(api: API, direction: Direction) -> None:
    match = trip(minutes_before=40, direction=direction)
    await api.add(match)
    params = {**RIDER, "direction": direction.value, "time": TIME.isoformat()}

    response = await search(api, routing(match), params=params)

    [result] = response.json()
    campus_end, driver_end = (
        ("destination", "origin") if direction == Direction.TO_CAMPUS else ("origin", "destination")
    )
    assert result["trip"][driver_end] is None
    assert result["trip"][campus_end]["label"] == "University of Manitoba, Fort Garry campus"
    assert HOME.label not in response.text


async def test_leaving_campus_is_priced_from_campus_to_the_drop_off(api: API) -> None:
    """A 6 km trip with the drop-off 1 km before the driver's end: the rider rides 5 km."""
    from_campus = trip(minutes_before=20, direction=Direction.FROM_CAMPUS)
    await api.add(from_campus)
    params = {**RIDER, "direction": "from_campus", "time": TIME.isoformat()}

    response = await search(api, routing(from_campus, to_end=1000), params=params)

    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["cost"] == {
        "amountCents": 225,  # 5 km at $0.45/km; not the 1 km after the drop-off
        "currency": "CAD",
        "explanation": "5.0 km at $0.45/km",
    }


async def test_only_matching_trips_soonest_first(api: API) -> None:
    late, early, unmatched = trip(20), trip(50), trip(35)
    await api.add(late, early, unmatched)

    response = await search(api, routing(late, early))

    assert response.status_code == 200, response.text
    assert [r["trip"]["id"] for r in response.json()] == [str(early.id), str(late.id)]


async def test_the_riders_own_trips_are_never_candidates(api: API) -> None:
    own = trip(40)
    own.driver_id = api.auth.user_id
    await api.add(own)

    response = await search(api, routing(own))

    assert response.json() == []


async def test_no_matches_is_an_empty_list(api: API) -> None:
    await api.add(trip(40))

    response = await search(api, routing())

    assert response.status_code == 200
    assert response.json() == []


async def test_no_candidates_never_calls_routing(api: API) -> None:
    far_future = (TIME + timedelta(days=300)).isoformat()
    params = {**RIDER, "direction": "to_campus", "time": far_future}

    response = await search(api, routing(), params=params)

    assert response.status_code == 200
    assert response.json() == []
    assert api.routing_requests == []


async def test_payments_not_ready_still_shows_the_trip_without_a_cost(api: API) -> None:
    """Payments' quote endpoint answers 501 until #99 lands."""
    match = trip(40)
    await api.add(match)

    def not_implemented(request: httpx.Request) -> httpx.Response:
        return httpx.Response(501, json={"code": "not_implemented"})

    response = await search(api, routing(match), payments=not_implemented)

    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["trip"]["id"] == str(match.id)
    assert result["cost"] is None


async def test_routing_down_returns_503(api: API) -> None:
    await api.add(trip(40))

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Routing is down", request=request)

    response = await search(api, down)

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_unavailable"
    assert response.json()["detail"] == "Matching is unavailable right now. Please try again."


async def test_requires_a_login(api: API) -> None:
    response = await search(api, routing(), headers={})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@pytest.mark.parametrize(
    "change",
    [
        {"lat": 120},
        {"lng": -200},
        {"direction": "to_downtown"},
        {"time": "2026-10-20T13:30:00"},  # no timezone
        {"time": "tomorrow"},
    ],
)
async def test_invalid_search_returns_422_without_calling_routing(
    api: API, change: dict[str, Any]
) -> None:
    params = {**RIDER, "direction": "to_campus", "time": TIME.isoformat(), **change}

    response = await search(api, routing(), params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    assert api.routing_requests == []
