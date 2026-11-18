"""POST /{trip_id}/requests with real PostgreSQL and mocked Routing and Payments."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import auto_accept_rules, outbox, seat_requests, trips
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


def accounts_not_called(request: httpx.Request) -> httpx.Response:
    """These drivers have no auto-accept rules, so Accounts is never asked for a rating (#43)."""
    raise AssertionError(f"Accounts was called: {request.url}")


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
                await connection.execute(
                    delete(auto_accept_rules).where(auto_accept_rules.c.driver_id == DRIVER_ID)
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
    payments_handler: Handler | Callable[[httpx.Request], Awaitable[httpx.Response]] | None = None,
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
        httpx.AsyncClient(
            transport=httpx.MockTransport(accounts_not_called), base_url="http://accounts:8000"
        ) as accounts_client,
    ):
        app.state.routing_client = routing_client
        app.state.payments_client = payments_client
        app.state.accounts_client = accounts_client
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


async def test_trip_cancelled_during_quote_cannot_get_a_pending_request(api: API) -> None:
    app, auth, _ = api
    trip = await add_trip(api)
    quoting = asyncio.Event()
    cancellation_committed = asyncio.Event()
    respond_to_payment = payments()

    async def paused_payments(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/quotes":
            quoting.set()
            await cancellation_committed.wait()
        return respond_to_payment(request)

    async with (
        asyncio.timeout(10),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
        asyncio.TaskGroup() as tasks,
    ):
        requesting = tasks.create_task(request_seat(api, trip.id, payments_handler=paused_payments))
        await quoting.wait()
        cancelled = await client.post(
            f"/{trip.id}/cancel",
            headers={
                **auth.headers(user_id=trip.driver_id),
                "X-Request-ID": str(auth.user_id),
            },
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "cancelled"
        cancellation_committed.set()

    response = requesting.result()
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "trip_not_open"
    assert await saved_requests(api) == []
    assert [event["type"] for event in await saved_events(api)] == ["TripCancelled"]


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


# ---------------------------------------------------------------- at the same time (#359)


async def request_together(
    api: API, requests: list[tuple[UUID, UUID]], routing_handler: Callable[[httpx.Request], Any]
) -> list[httpx.Response]:
    """Sends seat requests at the same moment: (trip, rider) each, sharing one app."""
    app, auth, _ = api
    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(routing_handler), base_url="http://routing:8000"
        ) as routing_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(payments()), base_url="http://payments:8000"
        ) as payments_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(accounts_not_called), base_url="http://accounts:8000"
        ) as accounts_client,
    ):
        app.state.routing_client = routing_client
        app.state.payments_client = payments_client
        app.state.accounts_client = accounts_client
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            sends: list[Awaitable[httpx.Response]] = [
                client.post(
                    f"/{trip_id}/requests",
                    json=BODY,
                    headers={
                        **auth.headers(user_id=rider_id),
                        "X-Request-ID": str(auth.user_id),
                    },
                )
                for trip_id, rider_id in requests
            ]
            return list(await asyncio.gather(*sends))


def slow_routing() -> Callable[[httpx.Request], Awaitable[httpx.Response]]:
    """Routing that takes a moment, so both requests are past their checks before either is
    saved, unless they're made to wait for each other."""
    answer = routing()

    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return answer(request)

    return handler


async def test_one_riders_simultaneous_requests_for_overlapping_trips(api: API) -> None:
    first, second = await add_trip(api), await add_trip(api)  # same time: they overlap
    rider = api[1].user_id

    responses = await request_together(api, [(first.id, rider), (second.id, rider)], slow_routing())

    assert sorted(r.status_code for r in responses) == [201, 409]
    [refused] = [r for r in responses if r.status_code == 409]
    assert refused.json()["code"] == "overlapping_request"
    assert len(await saved_requests(api)) == 1
    assert len(await saved_events(api)) == 1


async def test_two_riders_requesting_at_once_both_get_a_seat(api: API) -> None:
    trip = await add_trip(api)
    other_rider = uuid4()

    try:
        responses = await request_together(
            api, [(trip.id, api[1].user_id), (trip.id, other_rider)], slow_routing()
        )

        assert [r.status_code for r in responses] == [201, 201]
    finally:
        async with api[2].begin() as connection:
            await connection.execute(
                delete(seat_requests).where(seat_requests.c.rider_id == other_rider)
            )


async def set_rules(api: API, *, max_detour_minutes: int) -> None:
    """The trip's driver turns auto-accept on, with no minimum rating (#42)."""
    async with api[2].begin() as connection:
        await connection.execute(
            auto_accept_rules.insert().values(
                driver_id=DRIVER_ID, enabled=True, max_detour_minutes=max_detour_minutes
            )
        )


async def test_a_request_meeting_the_drivers_rules_is_auto_accepted(api: API) -> None:
    """#43: Routing says the pickup adds 180 seconds, within the driver's 5 minutes."""
    trip = await add_trip(api)
    await set_rules(api, max_detour_minutes=5)

    response = await request_seat(api, trip.id)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["autoAccepted"]) == ("accepted", True)
    assert body["decidedAt"] is not None

    [row] = await saved_requests(api)
    assert (row["status"], row["auto_accepted"], row["pickup_order"]) == ("accepted", True, 1)
    # Only RequestAccepted: seat-requested.v1 isn't published for an auto-accepted request.
    assert [event["type"] for event in await saved_events(api)] == ["RequestAccepted"]
    async with api[2].connect() as connection:
        seats = await connection.execute(
            select(trips.c.seats_available).where(trips.c.id == trip.id)
        )
        assert seats.scalar_one() == 2


async def test_a_request_over_the_drivers_detour_limit_stays_pending(api: API) -> None:
    trip = await add_trip(api)
    await set_rules(api, max_detour_minutes=2)  # 120 seconds, less than the 180 it adds

    response = await request_seat(api, trip.id)

    assert (response.json()["status"], response.json()["autoAccepted"]) == ("pending", False)
    assert [event["type"] for event in await saved_events(api)] == ["SeatRequested"]


@pytest.mark.parametrize("seats", [1, 2])
async def test_auto_accept_never_goes_over_the_seat_count(api: API, seats: int) -> None:
    """#44: five riders ask at the same moment for a trip that auto-accepts. Exactly as many
    are accepted as there are seats, and the seat count never goes below zero. The others
    are either left pending (saved before the seats went) or refused as full (they got
    there after), never accepted."""
    trip = await add_trip(api, seats_available=seats)
    await set_rules(api, max_detour_minutes=5)
    riders = [api[1].user_id, *(uuid4() for _ in range(4))]

    try:
        responses = await request_together(
            api, [(trip.id, rider) for rider in riders], slow_routing()
        )

        outcomes = sorted(
            r.json()["status"] if r.status_code == 201 else r.json()["code"] for r in responses
        )
        assert outcomes.count("accepted") == seats, outcomes
        assert set(outcomes) <= {"accepted", "pending", "trip_full"}, outcomes

        async with api[2].connect() as connection:
            left = await connection.execute(
                select(trips.c.seats_available).where(trips.c.id == trip.id)
            )
            assert left.scalar_one() == 0
            accepted = await connection.execute(
                select(func.count())
                .select_from(seat_requests)
                .where(seat_requests.c.trip_id == trip.id, seat_requests.c.status == "accepted")
            )
            assert accepted.scalar_one() == seats
    finally:
        async with api[2].begin() as connection:
            await connection.execute(
                delete(seat_requests).where(seat_requests.c.rider_id.in_(riders[1:]))
            )
