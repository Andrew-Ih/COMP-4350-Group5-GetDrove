"""Seats can't be oversold: many accepts at the same moment, on real PostgreSQL (#50)."""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import (
    SQLAlchemySeatRequestRepository,
)
from trips.adapters.persistence.tables import auto_accept_rules, outbox, seat_requests, trips
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type API = tuple[FastAPI, TestAuth, AsyncEngine]

RIDERS = 20
DEPARTURE = datetime.now(UTC) + timedelta(days=1)
BODY = {"lat": 49.821, "lng": -97.151, "pickupId": "s42"}
PICKUP = {
    "id": "s42",
    "label": "Pembina pickup",
    "lat": 49.82,
    "lng": -97.15,
    "walkSeconds": 120,
    "riderDistanceMeters": 4000,
}


async def routing_answers(request: httpx.Request) -> httpx.Response:
    """Routing: one pickup point, and every new pickup goes last. A short delay keeps
    requests overlapping."""
    await asyncio.sleep(0.05)
    if request.url.path == "/internal/pickup-points":
        return httpx.Response(200, json={"pickups": [PICKUP]})
    accepted = len(json.loads(request.content)["acceptedPickups"])
    return httpx.Response(
        200, json={"addedSeconds": 180, "position": accepted, "totalSeconds": 1080}
    )


def payments_answers(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/card"):
        rider = request.url.path.split("/")[3]
        return httpx.Response(200, json={"userId": rider, "hasCard": True})
    return httpx.Response(
        200,
        json={
            "amountCents": 200,
            "currency": "CAD",
            "explanation": "4 km at $0.45/km ($2.00 minimum)",
        },
    )


def accounts_not_called(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"Accounts was called: {request.url}")


@pytest.fixture
async def api() -> AsyncIterator[API]:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    engine = create_async_engine(get_settings().database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    clients = {
        "routing_client": httpx.AsyncClient(
            transport=httpx.MockTransport(routing_answers), base_url="http://routing:8000"
        ),
        "payments_client": httpx.AsyncClient(
            transport=httpx.MockTransport(payments_answers), base_url="http://payments:8000"
        ),
        "accounts_client": httpx.AsyncClient(
            transport=httpx.MockTransport(accounts_not_called), base_url="http://accounts:8000"
        ),
    }
    for name, client in clients.items():
        setattr(app.state, name, client)
    try:
        yield app, auth, engine
    finally:
        for client in clients.values():
            await client.aclose()
        try:
            async with engine.begin() as connection:
                driven = await connection.execute(
                    select(trips.c.id).where(trips.c.driver_id == auth.user_id)
                )
                trip_ids = list(driven.scalars().all())
                await connection.execute(
                    delete(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(auth.user_id)
                    )
                )
                await connection.execute(
                    delete(seat_requests).where(seat_requests.c.trip_id.in_(trip_ids))
                )
                await connection.execute(delete(trips).where(trips.c.id.in_(trip_ids)))
                await connection.execute(
                    delete(auto_accept_rules).where(auto_accept_rules.c.driver_id == auth.user_id)
                )
        finally:
            await engine.dispose()


async def seed_trip(api: API, *, seats: int) -> Trip:
    trip = Trip.create(
        driver_id=api[1].user_id,
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=DEPARTURE,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=seats,
    )
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemyTripRepository(session).add(trip)
    return trip


async def add_pending(api: API, trip: Trip) -> SeatRequest:
    request: SeatRequest = replace(
        SeatRequest.create(
            trip_id=trip.id,
            rider_id=uuid4(),
            pickup=Location("Pembina pickup", 49.82, -97.15),
            walk_seconds=120,
            rider_distance_meters=4000,
            detour_seconds=180,
            cost=Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)"),
            now=datetime.now(UTC) - timedelta(hours=1),
        ),
        status=RequestStatus.PENDING,
    )
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemySeatRequestRepository(session).add(request)
    return request


async def set_rules(api: API) -> None:
    """The trip's driver turns auto-accept on: up to 5 minutes of detour, any rating."""
    async with api[2].begin() as connection:
        await connection.execute(
            auto_accept_rules.insert().values(
                driver_id=api[1].user_id, enabled=True, max_detour_minutes=5
            )
        )


async def act(
    api: API, action: str, request_id: UUID, user_id: UUID | None = None
) -> httpx.Response:
    """accept / decline / cancel, as the trip's driver unless a user is given."""
    app, auth, _ = api
    headers = auth.headers() if user_id is None else auth.headers(user_id=user_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={**headers, "X-Request-ID": str(auth.user_id)},
    ) as client:
        return await client.post(f"/requests/{request_id}/{action}")


async def accept(api: API, request_id: UUID) -> httpx.Response:
    return await act(api, "accept", request_id)


async def accept_all(api: API, requests: list[SeatRequest]) -> list[httpx.Response]:
    return list(await asyncio.gather(*(accept(api, r.id) for r in requests)))


async def request_seat(api: API, trip: Trip, rider_id: UUID) -> httpx.Response:
    """A rider asks for a seat; with auto-accept on, this can accept it on the spot."""
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={**auth.headers(user_id=rider_id), "X-Request-ID": str(auth.user_id)},
    ) as client:
        return await client.post(f"/{trip.id}/requests", json=BODY)


async def seats_left(api: API, trip: Trip) -> int:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(trips.c.seats_available).where(trips.c.id == trip.id)
        )
        return result.scalar_one()


async def count_with_status(api: API, trip: Trip, status: RequestStatus) -> int:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(func.count())
            .select_from(seat_requests)
            .where(seat_requests.c.trip_id == trip.id)
            .where(seat_requests.c.status == status.value)
        )
        return result.scalar_one()


async def pickup_orders(api: API, trip: Trip) -> list[int | None]:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(seat_requests.c.pickup_order)
            .where(seat_requests.c.trip_id == trip.id)
            .where(seat_requests.c.status == RequestStatus.ACCEPTED.value)
            .order_by(seat_requests.c.pickup_order)
        )
        return list(result.scalars().all())


async def accepted_events(api: API) -> int:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(func.count())
            .select_from(outbox)
            .where(outbox.c.envelope["correlationId"].astext == str(api[1].user_id))
            .where(outbox.c.type == "RequestAccepted")
        )
        return result.scalar_one()


@pytest.mark.parametrize("attempt", range(3))  # repeated, to show it isn't flaky
async def test_twenty_riders_one_seat_exactly_one_is_accepted(api: API, attempt: int) -> None:
    trip = await seed_trip(api, seats=1)
    requests = [await add_pending(api, trip) for _ in range(RIDERS)]

    responses = await accept_all(api, requests)

    codes = sorted(response.status_code for response in responses)
    assert codes == [200] + [409] * (RIDERS - 1)
    losers = [response for response in responses if response.status_code == 409]
    assert {response.json()["code"] for response in losers} == {"seat_taken"}
    assert await seats_left(api, trip) == 0
    assert await count_with_status(api, trip, RequestStatus.ACCEPTED) == 1
    assert await count_with_status(api, trip, RequestStatus.PENDING) == RIDERS - 1
    assert await accepted_events(api) == 1


async def test_twenty_riders_three_seats_exactly_three_are_accepted(api: API) -> None:
    trip = await seed_trip(api, seats=3)
    requests = [await add_pending(api, trip) for _ in range(RIDERS)]

    responses = await accept_all(api, requests)

    assert sorted(response.status_code for response in responses) == [200] * 3 + [409] * 17
    assert await seats_left(api, trip) == 0
    assert await count_with_status(api, trip, RequestStatus.ACCEPTED) == 3
    assert await pickup_orders(api, trip) == [1, 2, 3]


@pytest.mark.parametrize("attempt", range(3))
async def test_auto_accept_racing_a_manual_accept_for_the_last_seat(api: API, attempt: int) -> None:
    """A rider's request would be auto-accepted at the same moment the driver accepts
    another rider by hand. One seat: exactly one of them gets it, whichever is first."""
    trip = await seed_trip(api, seats=1)
    waiting = await add_pending(api, trip)
    await set_rules(api)

    manual, automatic = await asyncio.gather(
        accept(api, waiting.id), request_seat(api, trip, uuid4())
    )

    assert await seats_left(api, trip) == 0
    assert await count_with_status(api, trip, RequestStatus.ACCEPTED) == 1
    assert await accepted_events(api) == 1
    if manual.status_code == 200:
        # The driver was first: the other request is pending or refused as full.
        assert (automatic.status_code, automatic.json().get("status")) in {
            (201, "pending"),
            (409, None),
        }
        if automatic.status_code == 409:
            assert automatic.json()["code"] == "trip_full"
    else:
        # Auto-accept was first: the driver's accept loses the seat.
        assert manual.status_code == 409
        assert manual.json()["code"] == "seat_taken"
        assert automatic.status_code == 201
        assert automatic.json()["status"] == "accepted"
        assert automatic.json()["autoAccepted"] is True


async def test_a_cancelled_seat_is_taken_by_the_next_rider_straight_away(api: API) -> None:
    trip = await seed_trip(api, seats=1)
    first, second = await add_pending(api, trip), await add_pending(api, trip)
    assert (await accept(api, first.id)).status_code == 200
    refused = await accept(api, second.id)
    assert (refused.status_code, refused.json()["code"]) == (409, "seat_taken")

    cancelled = await act(api, "cancel", first.id, user_id=first.rider_id)
    assert cancelled.status_code == 200
    taken = await accept(api, second.id)

    assert taken.status_code == 200
    assert await seats_left(api, trip) == 0
    assert await pickup_orders(api, trip) == [1]
