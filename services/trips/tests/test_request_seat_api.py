"""POST /{trip_id}/requests with real PostgreSQL and mocked Routing and Payments."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox, seat_requests, trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, TripStatus
from trips.infrastructure.main import create_app
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

type API = tuple[FastAPI, TestAuth, AsyncEngine]
type Handler = Callable[[httpx.Request], httpx.Response]

DRIVER_ID = uuid4()
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
                await connection.execute(
                    delete(seat_requests).where(seat_requests.c.rider_id == auth.user_id)
                )
                await connection.execute(
                    delete(trips).where(trips.c.driver_id.in_([auth.user_id, DRIVER_ID]))
                )
        finally:
            await engine.dispose()


def routing(*, empty: bool = False, fail_on: str | None = None, mode: str = "http") -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == fail_on:
            if mode == "timeout":
                raise httpx.ReadTimeout("Routing timed out", request=request)
            if mode == "json":
                return httpx.Response(200, content=b"not JSON")
            return httpx.Response(503)
        if request.url.path == "/internal/pickup-points":
            return httpx.Response(200, json={"pickups": [] if empty else [PICKUP]})
        if request.url.path == "/internal/detours":
            return httpx.Response(
                200, json={"addedSeconds": 180, "position": 0, "totalSeconds": 1080}
            )
        raise AssertionError(request.url.path)

    return handler


def payments(*, has_card: bool = True, fail: str | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/card"):
            if fail == "card":
                return httpx.Response(503)
            rider = request.url.path.split("/")[3]
            return httpx.Response(200, json={"userId": rider, "hasCard": has_card})
        if request.url.path == "/internal/quotes":
            if fail == "quote":
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "amountCents": 200,
                    "currency": "CAD",
                    "explanation": "4 km at $0.45/km ($2.00 minimum)",
                },
            )
        raise AssertionError(request.url.path)

    return handler


async def add_trip(
    api: API,
    *,
    driver_id: UUID = DRIVER_ID,
    seats_available: int | None = None,
    status: TripStatus = TripStatus.SCHEDULED,
) -> Trip:
    trip = Trip.create(
        driver_id=driver_id,
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=DEPARTURE,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    if seats_available is not None:
        trip.seats_available = seats_available
    trip.status = status
    factory = async_sessionmaker(api[2], expire_on_commit=False)
    async with factory() as session, session.begin():
        await SQLAlchemyTripRepository(session).add(trip)
    return trip


async def request_seat(
    api: API,
    trip_id: UUID,
    routing_handler: Handler | None = None,
    payments_handler: Handler | None = None,
    body: dict[str, Any] | None = None,
) -> httpx.Response:
    app, auth, _ = api
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(routing_handler or routing()),
            base_url="http://routing:8000",
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(payments_handler or payments()),
            base_url="http://payments:8000",
        ) as payments_client,
    ):
        app.state.routing_client = routing_client
        app.state.payments_client = payments_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={**auth.headers(), "X-Request-ID": str(auth.user_id)},
        ) as client:
            return await client.post(f"/{trip_id}/requests", json=body or BODY)


async def saved_requests(api: API) -> list[RowMapping]:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(seat_requests).where(seat_requests.c.rider_id == api[1].user_id)
        )
        return list(result.mappings())


async def saved_events(api: API) -> list[RowMapping]:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(outbox).where(outbox.c.envelope["correlationId"].astext == str(api[1].user_id))
        )
        return list(result.mappings())


async def assert_nothing_saved(api: API) -> None:
    assert await saved_requests(api) == []
    assert await saved_events(api) == []


async def test_valid_request_returns_201_and_saves_pending_request(api: API) -> None:
    trip = await add_trip(api)

    response = await request_seat(api, trip.id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tripId"] == str(trip.id)
    assert body["riderId"] == str(api[1].user_id)
    assert body["status"] == "pending"
    assert body["autoAccepted"] is False
    assert body["decidedAt"] is None
    assert body["pickup"]["label"] == "Pembina pickup"
    assert body["pickup"]["walkSeconds"] == 120
    assert body["cost"]["amountCents"] == 200
    assert body["cost"]["currency"] == "CAD"

    rows = await saved_requests(api)
    assert len(rows) == 1
    assert str(rows[0]["id"]) == body["id"]
    assert rows[0]["status"] == "pending"
    assert rows[0]["detour_seconds"] == 180
    assert rows[0]["rider_distance_meters"] == 4000
    assert rows[0]["amount_cents"] == 200

    events = await saved_events(api)
    assert len(events) == 1
    assert events[0]["type"] == "SeatRequested"
    payload = events[0]["envelope"]["payload"]
    assert payload["requestId"] == body["id"]
    assert payload["driverId"] == str(DRIVER_ID)

    async with api[2].connect() as connection:
        seats = await connection.execute(
            select(trips.c.seats_available).where(trips.c.id == trip.id)
        )
        assert seats.scalar_one() == 3


async def test_own_trip_returns_403(api: API) -> None:
    trip = await add_trip(api, driver_id=api[1].user_id)

    response = await request_seat(api, trip.id)

    assert response.status_code == 403
    assert response.json()["code"] == "own_trip"
    await assert_nothing_saved(api)


async def test_unknown_trip_returns_404(api: API) -> None:
    response = await request_seat(api, uuid4())

    assert response.status_code == 404
    assert response.json()["code"] == "trip_not_found"
    await assert_nothing_saved(api)


@pytest.mark.parametrize(
    ("options", "code"),
    [
        ({"seats_available": 0}, "trip_full"),
        ({"status": TripStatus.CANCELLED}, "trip_not_open"),
    ],
)
async def test_closed_or_full_trip_returns_409(
    api: API, options: dict[str, Any], code: str
) -> None:
    trip = await add_trip(api, **options)

    response = await request_seat(api, trip.id)

    assert response.status_code == 409
    assert response.json()["code"] == code
    await assert_nothing_saved(api)


async def test_second_request_on_same_trip_returns_409(api: API) -> None:
    trip = await add_trip(api)
    assert (await request_seat(api, trip.id)).status_code == 201

    response = await request_seat(api, trip.id)

    assert response.status_code == 409
    assert response.json()["code"] == "already_requested"
    assert len(await saved_requests(api)) == 1
    assert len(await saved_events(api)) == 1


async def test_overlapping_trip_returns_409(api: API) -> None:
    first = await add_trip(api)
    second = await add_trip(api)
    assert (await request_seat(api, first.id)).status_code == 201

    response = await request_seat(api, second.id)

    assert response.status_code == 409
    assert response.json()["code"] == "overlapping_request"
    assert len(await saved_requests(api)) == 1
    assert len(await saved_events(api)) == 1


async def test_missing_card_returns_409(api: API) -> None:
    trip = await add_trip(api)

    response = await request_seat(api, trip.id, payments_handler=payments(has_card=False))

    assert response.status_code == 409
    assert response.json()["code"] == "card_required"
    await assert_nothing_saved(api)


async def test_unavailable_pickup_returns_422(api: API) -> None:
    trip = await add_trip(api)

    response = await request_seat(api, trip.id, routing_handler=routing(empty=True))

    assert response.status_code == 422
    assert response.json()["code"] == "pickup_not_available"
    await assert_nothing_saved(api)


@pytest.mark.parametrize("fail_on", ["/internal/pickup-points", "/internal/detours"])
@pytest.mark.parametrize("mode", ["http", "timeout", "json"])
async def test_routing_failure_returns_503_and_saves_nothing(
    api: API, fail_on: str, mode: str
) -> None:
    trip = await add_trip(api)

    response = await request_seat(api, trip.id, routing_handler=routing(fail_on=fail_on, mode=mode))

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "routing_unavailable"
    await assert_nothing_saved(api)


@pytest.mark.parametrize("fail", ["card", "quote"])
async def test_payments_failure_returns_503_and_saves_nothing(api: API, fail: str) -> None:
    trip = await add_trip(api)

    response = await request_seat(api, trip.id, payments_handler=payments(fail=fail))

    assert response.status_code == 503, response.text
    assert response.json()["code"] == "payments_unavailable"
    await assert_nothing_saved(api)


@pytest.mark.parametrize(
    "change",
    [{"lat": 91}, {"lng": -181}, {"pickupId": ""}, {"pickupId": None}],
)
async def test_invalid_body_returns_422_and_calls_nothing(api: API, change: dict[str, Any]) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("No service should be called for invalid input")

    trip = await add_trip(api)

    response = await request_seat(
        api,
        trip.id,
        routing_handler=unexpected,
        payments_handler=unexpected,
        body={**BODY, **change},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
    await assert_nothing_saved(api)
