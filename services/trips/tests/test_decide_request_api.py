"""Accept, decline and cancel endpoints with real PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import (
    SQLAlchemySeatRequestRepository,
)
from trips.adapters.persistence.tables import outbox, seat_requests, trips
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type API = tuple[FastAPI, TestAuth, AsyncEngine]

DEPARTURE = datetime.now(UTC) + timedelta(days=1)


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
                mine = await connection.execute(
                    select(seat_requests.c.trip_id).where(seat_requests.c.rider_id == auth.user_id)
                )
                driven = await connection.execute(
                    select(trips.c.id).where(trips.c.driver_id == auth.user_id)
                )
                trip_ids = [*mine.scalars().all(), *driven.scalars().all()]
                await connection.execute(
                    delete(outbox).where(
                        outbox.c.envelope["correlationId"].astext == str(auth.user_id)
                    )
                )
                await connection.execute(
                    delete(seat_requests).where(seat_requests.c.trip_id.in_(trip_ids))
                )
                await connection.execute(delete(trips).where(trips.c.id.in_(trip_ids)))
        finally:
            await engine.dispose()


async def add_request(
    api: API, trip: Trip, rider_id: UUID, status: RequestStatus = RequestStatus.PENDING
) -> SeatRequest:
    request = replace(
        SeatRequest.create(
            trip_id=trip.id,
            rider_id=rider_id,
            pickup=Location("Pembina pickup", 49.82, -97.15),
            walk_seconds=120,
            rider_distance_meters=4000,
            detour_seconds=180,
            cost=Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)"),
            now=datetime.now(UTC) - timedelta(hours=1),
        ),
        status=status,
    )
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemySeatRequestRepository(session).add(request)
    return request


async def seed(
    api: API,
    *,
    as_driver: bool,
    status: RequestStatus = RequestStatus.PENDING,
    seats_available: int = 3,
) -> tuple[Trip, SeatRequest]:
    me = api[1].user_id
    trip = Trip.create(
        driver_id=me if as_driver else uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=DEPARTURE,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    trip.seats_available = seats_available
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemyTripRepository(session).add(trip)
    request = await add_request(api, trip, uuid4() if as_driver else me, status)
    return trip, request


async def act(api: API, action: str, request_id: UUID) -> httpx.Response:
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
    ) as client:
        return await client.post(f"/requests/{request_id}/{action}")


async def seats_left(api: API, trip: Trip) -> int:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(trips.c.seats_available).where(trips.c.id == trip.id)
        )
        return result.scalar_one()


async def stored_status(api: API, request: SeatRequest) -> str:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(seat_requests.c.status).where(seat_requests.c.id == request.id)
        )
        return result.scalar_one()


async def saved_events(api: API) -> list[RowMapping]:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(outbox).where(outbox.c.envelope["correlationId"].astext == str(api[1].user_id))
        )
        return list(result.mappings())


# ---------------------------------------------------------------- accept


async def test_driver_accepts_and_a_seat_is_taken(api: API) -> None:
    trip, request = await seed(api, as_driver=True)

    response = await act(api, "accept", request.id)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"
    assert await stored_status(api, request) == "accepted"
    assert await seats_left(api, trip) == 2
    events = await saved_events(api)
    assert [event["type"] for event in events] == ["RequestAccepted"]
    payload = events[0]["envelope"]["payload"]
    assert payload["requestId"] == str(request.id)
    assert payload["amountCents"] == 200
    assert payload["autoAccepted"] is False


async def test_a_rider_cannot_accept(api: API) -> None:
    trip, request = await seed(api, as_driver=False)

    response = await act(api, "accept", request.id)

    assert response.status_code == 403
    assert response.json()["code"] == "not_trip_driver"
    assert await stored_status(api, request) == "pending"
    assert await seats_left(api, trip) == 3
    assert await saved_events(api) == []


async def test_accepting_an_unknown_request_returns_404(api: API) -> None:
    response = await act(api, "accept", uuid4())

    assert response.status_code == 404
    assert response.json()["code"] == "request_not_found"


async def test_accepting_a_cancelled_request_returns_409(api: API) -> None:
    trip, request = await seed(api, as_driver=True, status=RequestStatus.CANCELLED)

    response = await act(api, "accept", request.id)

    assert response.status_code == 409
    assert response.json()["code"] == "request_not_pending"
    assert await seats_left(api, trip) == 3
    assert await saved_events(api) == []


async def test_accepting_with_no_seat_left_returns_seat_taken_and_stays_pending(
    api: API,
) -> None:
    trip, request = await seed(api, as_driver=True, seats_available=0)

    response = await act(api, "accept", request.id)

    assert response.status_code == 409
    assert response.json()["code"] == "seat_taken"
    assert await stored_status(api, request) == "pending"
    assert await seats_left(api, trip) == 0
    assert await saved_events(api) == []


async def test_two_requests_race_for_the_last_seat(api: API) -> None:
    trip, first = await seed(api, as_driver=True, seats_available=1)
    second = await add_request(api, trip, uuid4())

    responses = await asyncio.gather(act(api, "accept", first.id), act(api, "accept", second.id))

    assert sorted(response.status_code for response in responses) == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["code"] == "seat_taken"
    assert await seats_left(api, trip) == 0
    statuses = sorted([await stored_status(api, first), await stored_status(api, second)])
    assert statuses == ["accepted", "pending"]
    assert [event["type"] for event in await saved_events(api)] == ["RequestAccepted"]


# ---------------------------------------------------------------- decline


async def test_declining_an_accepted_request_gives_the_seat_back(api: API) -> None:
    trip, request = await seed(
        api, as_driver=True, status=RequestStatus.ACCEPTED, seats_available=2
    )

    response = await act(api, "decline", request.id)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "declined"
    assert await seats_left(api, trip) == 3
    events = await saved_events(api)
    assert [event["type"] for event in events] == ["RequestDeclined"]
    assert events[0]["envelope"]["payload"]["wasAccepted"] is True


async def test_declining_a_pending_request_keeps_the_seats(api: API) -> None:
    trip, request = await seed(api, as_driver=True)

    response = await act(api, "decline", request.id)

    assert response.status_code == 200
    assert await seats_left(api, trip) == 3
    events = await saved_events(api)
    assert events[0]["envelope"]["payload"]["wasAccepted"] is False


async def test_a_rider_cannot_decline(api: API) -> None:
    _, request = await seed(api, as_driver=False)

    response = await act(api, "decline", request.id)

    assert response.status_code == 403
    assert response.json()["code"] == "not_trip_driver"
    assert await saved_events(api) == []


async def test_declining_a_declined_request_returns_409(api: API) -> None:
    _, request = await seed(api, as_driver=True, status=RequestStatus.DECLINED)

    response = await act(api, "decline", request.id)

    assert response.status_code == 409
    assert response.json()["code"] == "request_not_decidable"
    assert await saved_events(api) == []


# ---------------------------------------------------------------- cancel


async def test_cancelling_an_accepted_request_gives_the_seat_back(api: API) -> None:
    trip, request = await seed(
        api, as_driver=False, status=RequestStatus.ACCEPTED, seats_available=2
    )

    response = await act(api, "cancel", request.id)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert await seats_left(api, trip) == 3
    events = await saved_events(api)
    assert [event["type"] for event in events] == ["RequestCancelled"]
    assert events[0]["envelope"]["payload"]["wasAccepted"] is True


async def test_the_driver_cannot_cancel_a_riders_request(api: API) -> None:
    _, request = await seed(api, as_driver=True)

    response = await act(api, "cancel", request.id)

    assert response.status_code == 403
    assert response.json()["code"] == "not_your_request"
    assert await stored_status(api, request) == "pending"
    assert await saved_events(api) == []


async def test_cancelling_twice_publishes_once_and_frees_one_seat(api: API) -> None:
    trip, request = await seed(
        api, as_driver=False, status=RequestStatus.ACCEPTED, seats_available=2
    )

    first = await act(api, "cancel", request.id)
    second = await act(api, "cancel", request.id)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "request_not_cancellable"
    assert await seats_left(api, trip) == 3
    assert len(await saved_events(api)) == 1
