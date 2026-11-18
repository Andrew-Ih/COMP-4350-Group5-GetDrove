"""Accept, decline and cancel endpoints with real PostgreSQL."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete, select, update
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
from trips.domain.values import Direction, Location, Quote, TripStatus
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
    # Accepting asks Routing where the pickup goes on the route (#360): by default, last.
    app.state.routing_client = httpx.AsyncClient(
        transport=httpx.MockTransport(detours(lambda accepted: accepted)),
        base_url="http://routing:8000",
    )
    try:
        yield app, auth, engine
    finally:
        await app.state.routing_client.aclose()
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


def detours(position: Callable[[int], int] | None) -> Callable[[httpx.Request], httpx.Response]:
    """Routing's ``/internal/detours``: the position for the new pickup, from how many are
    accepted already; ``None`` means Routing is down."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/detours"
        if position is None:
            return httpx.Response(503, json={"code": "routing_engine_unavailable"})
        accepted = len(json.loads(request.content)["acceptedPickups"])
        return httpx.Response(
            200, json={"addedSeconds": 60, "position": position(accepted), "totalSeconds": 900}
        )

    return handler


def use_routing(
    api: API,
    handler: Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]],
) -> None:
    api[0].state.routing_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    )


async def pickup_order(api: API, request: SeatRequest) -> int | None:
    async with api[2].connect() as connection:
        result = await connection.execute(
            select(seat_requests.c.pickup_order).where(seat_requests.c.id == request.id)
        )
        return result.scalar_one()


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
    departure_at: datetime = DEPARTURE,
    trip_status: TripStatus = TripStatus.SCHEDULED,
    direction: Direction = Direction.TO_CAMPUS,
) -> tuple[Trip, SeatRequest]:
    me = api[1].user_id
    trip = Trip.create(
        driver_id=me if as_driver else uuid4(),
        direction=direction,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=departure_at,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    trip.seats_available = seats_available
    trip.status = trip_status
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
    assert payload["direction"] == "to_campus"


@pytest.mark.parametrize("direction", [Direction.TO_CAMPUS, Direction.FROM_CAMPUS])
async def test_the_accepted_event_says_which_way_the_trip_goes(
    api: API, direction: Direction
) -> None:
    """So Notifications can tell the pickup (to campus) from the drop-off (leaving) (#354)."""
    _, request = await seed(api, as_driver=True, direction=direction)

    response = await act(api, "accept", request.id)

    assert response.status_code == 200, response.text
    [event] = await saved_events(api)
    payload = event["envelope"]["payload"]
    assert payload["direction"] == direction.value
    assert payload["pickupLabel"] == "Pembina pickup"


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


async def test_accepting_after_departure_returns_409_and_takes_no_seat(api: API) -> None:
    trip, request = await seed(
        api, as_driver=True, departure_at=datetime.now(UTC) - timedelta(minutes=5)
    )

    response = await act(api, "accept", request.id)

    assert response.status_code == 409
    assert response.json()["code"] == "request_not_pending"
    assert await stored_status(api, request) == "pending"
    assert await seats_left(api, trip) == 3
    assert await saved_events(api) == []


async def test_accepting_on_a_cancelled_trip_is_not_seat_taken(api: API) -> None:
    _, request = await seed(api, as_driver=True, trip_status=TripStatus.CANCELLED)

    response = await act(api, "accept", request.id)

    assert response.status_code == 409
    assert response.json()["code"] == "request_not_pending"
    assert await stored_status(api, request) == "pending"
    assert await saved_events(api) == []


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


# ---------------------------------------------------------------- read one (#358)


async def read(api: API, request_id: UUID, user_id: UUID | None = None) -> httpx.Response:
    app, auth, _ = api
    headers = auth.headers() if user_id is None else auth.headers(user_id=user_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers=headers,
    ) as client:
        return await client.get(f"/requests/{request_id}")


@pytest.mark.parametrize(
    "status",
    [
        RequestStatus.PENDING,
        RequestStatus.ACCEPTED,
        RequestStatus.DECLINED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
        RequestStatus.PAYMENT_FAILED,
    ],
)
async def test_the_rider_reads_their_request(api: API, status: RequestStatus) -> None:
    _, request = await seed(api, as_driver=False, status=status)

    response = await read(api, request.id)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(request.id)
    assert response.json()["status"] == status.value


async def test_the_rider_sees_their_request_accepted(api: API) -> None:
    """What the trip screen's polling sees once the driver accepts."""
    _, request = await seed(api, as_driver=False)
    assert (await read(api, request.id)).json()["status"] == "pending"

    async with async_sessionmaker(api[2], expire_on_commit=False)() as session, session.begin():
        repository = SQLAlchemySeatRequestRepository(session)
        accepted = request.accept(datetime.now(UTC))
        assert await repository.save_decision(accepted, expected=RequestStatus.PENDING)

    assert (await read(api, request.id)).json()["status"] == "accepted"


async def test_the_trips_driver_reads_a_request_on_it(api: API) -> None:
    _, request = await seed(api, as_driver=True)

    response = await read(api, request.id)

    assert response.status_code == 200, response.text
    assert response.json()["riderId"] == str(request.rider_id)


async def test_someone_else_gets_403(api: API) -> None:
    _, request = await seed(api, as_driver=True)

    response = await read(api, request.id, user_id=uuid4())

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "forbidden"


async def test_an_unknown_request_is_404(api: API) -> None:
    response = await read(api, uuid4())

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "request_not_found"


# ---------------------------------------------------------------- placing on accept (#360)


async def test_accepting_places_the_pickup_where_routing_says_now(api: API) -> None:
    """Routing puts each new pickup first on the route; the saved positions (none) would have
    put them last."""
    trip, first = await seed(api, as_driver=True)
    second = await add_request(api, trip, uuid4())
    original = api[0].state.routing_client
    use_routing(api, detours(lambda accepted: 0))
    try:
        assert (await act(api, "accept", first.id)).status_code == 200
        assert (await act(api, "accept", second.id)).status_code == 200
    finally:
        await api[0].state.routing_client.aclose()
        api[0].state.routing_client = original

    assert await pickup_order(api, second) == 1
    assert await pickup_order(api, first) == 2


async def test_with_routing_down_accepting_still_works(api: API) -> None:
    trip, request = await seed(api, as_driver=True)
    original = api[0].state.routing_client
    use_routing(api, detours(None))
    try:
        response = await act(api, "accept", request.id)
    finally:
        await api[0].state.routing_client.aclose()
        api[0].state.routing_client = original

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"
    assert await pickup_order(api, request) == 1
    assert await seats_left(api, trip) == 2


# ---------------------------------------------------------------- at the same time


async def act_as(api: API, action: str, request_id: UUID, user_id: UUID) -> httpx.Response:
    app, auth, _ = api
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={**auth.headers(user_id=user_id), "X-Request-ID": str(auth.user_id)},
    ) as client:
        return await client.post(f"/requests/{request_id}/{action}")


async def test_accepting_and_a_cancel_at_once_on_one_trip_dont_deadlock(api: API) -> None:
    """The accept moves the cancelling rider's pickup down while the cancel frees their seat.
    Both lock the trip first, so one waits for the other instead of a deadlock."""
    trip, seated = await seed(api, as_driver=True)
    assert (await act(api, "accept", seated.id)).status_code == 200  # pickup 1
    newcomer = await add_request(api, trip, uuid4())

    async def slow_first(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)  # the accept holds the trip while Routing answers
        return detours(lambda accepted: 0)(request)  # the newcomer goes first

    original = api[0].state.routing_client
    use_routing(api, slow_first)
    try:

        async def cancel_soon() -> httpx.Response:
            await asyncio.sleep(0.05)  # after the accept has started
            return await act_as(api, "cancel", seated.id, seated.rider_id)

        accepted, cancelled = await asyncio.gather(act(api, "accept", newcomer.id), cancel_soon())
    finally:
        await api[0].state.routing_client.aclose()
        api[0].state.routing_client = original

    assert (accepted.status_code, cancelled.status_code) == (200, 200), (
        accepted.text,
        cancelled.text,
    )
    assert await stored_status(api, seated) == "cancelled"
    assert await pickup_order(api, seated) is None
    assert await pickup_order(api, newcomer) == 1
    assert await seats_left(api, trip) == 2


@pytest.mark.parametrize("leave_action", ["decline", "cancel"])
async def test_saved_share_survives_acceptance_and_other_riders_joining_or_leaving(
    api: API, leave_action: str
) -> None:
    """Acceptance exports the saved quote even if today's pricing would differ (#69)."""
    trip, original = await seed(api, as_driver=True)
    # A historical quote deliberately differs from today's quote for 4 km.
    saved = {"amount_cents": 625, "currency": "CAD", "rider_distance_meters": 4000}
    async with api[2].begin() as connection:
        await connection.execute(
            update(seat_requests)
            .where(seat_requests.c.id == original.id)
            .values(**saved, cost_explanation="Saved earlier")
        )

    def payments_must_not_be_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Acceptance must use the saved quote without calling Payments")

    async def original_quote() -> dict[str, object]:
        async with api[2].connect() as connection:
            row = (
                (
                    await connection.execute(
                        select(seat_requests).where(seat_requests.c.id == original.id)
                    )
                )
                .mappings()
                .one()
            )
            return {key: row[key] for key in saved}

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(payments_must_not_be_called), base_url="http://payments"
    ) as payments:
        api[0].state.payments_client = payments
        accepted = await act(api, "accept", original.id)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["cost"]["amountCents"] == saved["amount_cents"]
        assert accepted.json()["cost"]["currency"] == saved["currency"]
        assert await original_quote() == saved

        other = await add_request(api, trip, uuid4())
        joined = await act(api, "accept", other.id)
        assert joined.status_code == 200, joined.text
        assert await original_quote() == saved

        if leave_action == "decline":
            left = await act(api, "decline", other.id)
        else:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api[0]), base_url="http://test"
            ) as client:
                left = await client.post(
                    f"/requests/{other.id}/cancel",
                    headers={
                        **api[1].headers(user_id=other.rider_id),
                        "X-Request-ID": str(api[1].user_id),
                    },
                )
        assert left.status_code == 200, left.text
        assert await original_quote() == saved

    events = await saved_events(api)
    [accepted_event] = [
        row
        for row in events
        if row["type"] == "RequestAccepted"
        and row["envelope"]["payload"]["requestId"] == str(original.id)
    ]
    assert accepted_event["envelope"]["payload"]["amountCents"] == saved["amount_cents"]
    assert accepted_event["envelope"]["payload"]["currency"] == saved["currency"]
