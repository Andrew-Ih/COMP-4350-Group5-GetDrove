"""GET /{trip_id}/requests with real PostgreSQL and a mocked Accounts."""

from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import (
    SQLAlchemySeatRequestRepository,
)
from trips.adapters.persistence.tables import seat_requests, trips
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type API = tuple[FastAPI, TestAuth, AsyncEngine]
type Handler = Callable[[httpx.Request], httpx.Response]

OTHER_DRIVER_ID = uuid4()
DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)


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
            drivers = [auth.user_id, OTHER_DRIVER_ID]
            async with engine.begin() as connection:
                await connection.execute(
                    delete(seat_requests).where(
                        seat_requests.c.trip_id.in_(
                            select(trips.c.id).where(trips.c.driver_id.in_(drivers))
                        )
                    )
                )
                await connection.execute(delete(trips).where(trips.c.driver_id.in_(drivers)))
        finally:
            await engine.dispose()


def accounts(names: Mapping[UUID, str], fail: str | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail == "timeout":
            raise httpx.ReadTimeout("Accounts timed out", request=request)
        if fail == "connect-error":
            raise httpx.ConnectError("Accounts is down", request=request)
        if fail == "http-error":
            return httpx.Response(503)
        if fail == "no-content":
            return httpx.Response(204)
        if fail == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if request.url.path != "/internal/users":
            raise AssertionError(request.url.path)
        ids = [UUID(value) for value in request.url.params.get_list("ids")]
        return httpx.Response(
            200,
            json={
                "users": [
                    {
                        "id": str(rider_id),
                        "firstName": names[rider_id],
                        "rating": 4.5,
                        "ratingCount": 12,
                        "noShowCount": 1,
                    }
                    for rider_id in ids
                    if rider_id in names
                ]
            },
        )

    return handler


def unexpected(request: httpx.Request) -> httpx.Response:
    pytest.fail("Accounts should not be called")


async def add_trip(api: API, *, driver_id: UUID) -> Trip:
    trip = Trip.create(
        driver_id=driver_id,
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=DEPARTURE,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemyTripRepository(session).add(trip)
    return trip


async def add_request(
    api: API, trip: Trip, status: RequestStatus, day: int, rider_id: UUID | None = None
) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=rider_id or uuid4(),
        pickup=Location(f"Pickup {day}", 49.815, -97.14),
        walk_seconds=120,
        rider_distance_meters=4000,
        detour_seconds=180,
        cost=Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)"),
        now=datetime(2029, 12, day, tzinfo=UTC),
    )
    request = replace(request, status=status)
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemySeatRequestRepository(session).add(request)
    return request


async def list_requests(
    api: API, trip_id: UUID, accounts_handler: Handler | None = None
) -> httpx.Response:
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(accounts_handler or accounts({})),
        base_url="http://accounts:8000",
    ) as accounts_client:
        app.state.accounts_client = accounts_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
        ) as client:
            return await client.get(f"/{trip_id}/requests")


async def test_driver_sees_pending_first_then_accepted_in_pickup_order(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)
    first_accepted = await add_request(api, trip, RequestStatus.ACCEPTED, 1)
    first_pending = await add_request(api, trip, RequestStatus.PENDING, 2)
    second_accepted = await add_request(api, trip, RequestStatus.ACCEPTED, 3)
    second_pending = await add_request(api, trip, RequestStatus.PENDING, 4)
    names = {
        request.rider_id: name
        for request, name in [
            (first_accepted, "Ana"),
            (first_pending, "Ben"),
            (second_accepted, "Cai"),
            (second_pending, "Dee"),
        ]
    }

    response = await list_requests(api, trip.id, accounts(names))

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body] == [
        str(first_pending.id),
        str(second_pending.id),
        str(first_accepted.id),
        str(second_accepted.id),
    ]
    assert [item["status"] for item in body] == ["pending", "pending", "accepted", "accepted"]
    assert [item["pickupOrder"] for item in body] == [None, None, 1, 2]
    assert [item["rider"]["firstName"] for item in body] == ["Ben", "Dee", "Ana", "Cai"]


async def test_each_request_shows_rider_pickup_detour_and_cost(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)
    request = await add_request(api, trip, RequestStatus.PENDING, 1)

    response = await list_requests(api, trip.id, accounts({request.rider_id: "Priya"}))

    assert response.status_code == 200, response.text
    [item] = response.json()
    assert item["rider"]["id"] == str(request.rider_id)
    assert item["rider"]["firstName"] == "Priya"
    assert item["rider"]["rating"] == 4.5
    assert item["rider"]["ratingCount"] == 12
    assert item["rider"]["noShowCount"] == 1
    assert item["pickup"]["label"] == "Pickup 1"
    assert item["detourSeconds"] == 180
    assert item["cost"]["amountCents"] == 200
    assert item["autoAccepted"] is False
    assert item["decidedAt"] is None


async def test_trip_without_requests_returns_empty_list_and_skips_accounts(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)

    response = await list_requests(api, trip.id, unexpected)

    assert response.status_code == 200
    assert response.json() == []


async def test_rider_unknown_to_accounts_is_skipped(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)
    lost = await add_request(api, trip, RequestStatus.ACCEPTED, 1)
    kept = await add_request(api, trip, RequestStatus.ACCEPTED, 2)

    response = await list_requests(api, trip.id, accounts({kept.rider_id: "Kim"}))

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body] == [str(kept.id)]
    assert str(lost.id) not in response.text
    assert body[0]["pickupOrder"] == 2


@pytest.mark.parametrize(
    "fail", ["timeout", "connect-error", "http-error", "no-content", "invalid-json"]
)
async def test_accounts_failure_returns_503(api: API, fail: str) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)
    request = await add_request(api, trip, RequestStatus.PENDING, 1)

    response = await list_requests(api, trip.id, accounts({request.rider_id: "Priya"}, fail))

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "accounts_unavailable"


async def test_other_drivers_trip_returns_403_and_skips_accounts(api: API) -> None:
    trip = await add_trip(api, driver_id=OTHER_DRIVER_ID)
    await add_request(api, trip, RequestStatus.PENDING, 1)

    response = await list_requests(api, trip.id, unexpected)

    assert response.status_code == 403
    assert response.json()["code"] == "not_trip_driver"


async def test_unknown_trip_returns_404_and_skips_accounts(api: API) -> None:
    response = await list_requests(api, uuid4(), unexpected)

    assert response.status_code == 404
    assert response.json()["code"] == "trip_not_found"


async def test_accounts_is_called_after_the_database_connection_is_released(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)
    request = await add_request(api, trip, RequestStatus.PENDING, 1)
    in_use: list[int] = []
    inner = accounts({request.rider_id: "Priya"})

    def handler(http_request: httpx.Request) -> httpx.Response:
        in_use.append(cast(QueuePool, api[2].pool).checkedout())
        return inner(http_request)

    response = await list_requests(api, trip.id, handler)

    assert response.status_code == 200, response.text
    assert in_use == [0]
