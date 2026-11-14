"""Seat-request persistence and active-request uniqueness in PostgreSQL."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import (
    SQLAlchemySeatRequestRepository,
)
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote, TripStatus

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
async def session(trips_database: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(trips_database)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection) as database_session:
                    yield database_session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def add_trip(session: AsyncSession, departure_at: datetime = DEPARTURE) -> Trip:
    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=departure_at,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    await SQLAlchemyTripRepository(session).add(trip)
    return trip


def make_request(
    trip: Trip,
    rider_id: UUID | None = None,
    status: RequestStatus = RequestStatus.PENDING,
    now: datetime = datetime(2029, 12, 31, tzinfo=UTC),
) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=rider_id or uuid4(),
        pickup=Location("Pickup point", 49.815, -97.14),
        walk_seconds=120,
        rider_distance_meters=4000,
        detour_seconds=180,
        cost=Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)"),
        now=now,
    )
    return replace(request, status=status)


async def test_saved_request_round_trips(session: AsyncSession) -> None:
    trip = await add_trip(session)
    request = make_request(trip)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    assert await repository.get(request.id) == request


async def test_missing_request_returns_none(session: AsyncSession) -> None:
    repository = SQLAlchemySeatRequestRepository(session)

    assert await repository.get(uuid4()) is None


async def test_unknown_detour_round_trips(session: AsyncSession) -> None:
    trip = await add_trip(session)
    request = replace(make_request(trip), detour_seconds=None)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    loaded = await repository.get(request.id)

    assert loaded is not None
    assert loaded.detour_seconds is None


@pytest.mark.parametrize("status", [RequestStatus.PENDING, RequestStatus.ACCEPTED])
async def test_pending_and_accepted_requests_are_active(
    session: AsyncSession, status: RequestStatus
) -> None:
    trip = await add_trip(session)
    request = make_request(trip, status=status)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    assert await repository.get_active_for_trip(trip.id, request.rider_id) == request


@pytest.mark.parametrize("first", [RequestStatus.PENDING, RequestStatus.ACCEPTED])
async def test_duplicate_active_request_is_rejected(
    session: AsyncSession, first: RequestStatus
) -> None:
    trip = await add_trip(session)
    rider_id = uuid4()
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(make_request(trip, rider_id, first))

    with pytest.raises(IntegrityError):
        await repository.add(make_request(trip, rider_id))


@pytest.mark.parametrize(
    "inactive",
    [
        RequestStatus.DECLINED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
        RequestStatus.PAYMENT_FAILED,
    ],
)
async def test_inactive_request_allows_a_new_request(
    session: AsyncSession, inactive: RequestStatus
) -> None:
    trip = await add_trip(session)
    rider_id = uuid4()
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(make_request(trip, rider_id, inactive))
    assert await repository.get_active_for_trip(trip.id, rider_id) is None

    fresh = make_request(trip, rider_id)
    await repository.add(fresh)

    assert await repository.get_active_for_trip(trip.id, rider_id) == fresh


async def test_different_riders_can_request_the_same_trip(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)

    await repository.add(make_request(trip))
    await repository.add(make_request(trip))


async def test_request_requires_an_existing_trip(session: AsyncSession) -> None:
    trip = await add_trip(session)
    missing_trip = replace(make_request(trip), trip_id=uuid4())
    repository = SQLAlchemySeatRequestRepository(session)

    with pytest.raises(IntegrityError):
        await repository.add(missing_trip)


@pytest.mark.parametrize(
    ("start", "end", "overlaps"),
    [(-30, 0, False), (-30, 1, True), (0, 15, True), (14, 30, True), (15, 30, False)],
)
async def test_overlap_boundaries(
    session: AsyncSession, start: int, end: int, overlaps: bool
) -> None:
    trip = await add_trip(session)
    request = make_request(trip)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    result = await repository.has_overlapping_active_request(
        request.rider_id,
        DEPARTURE + timedelta(minutes=start),
        DEPARTURE + timedelta(minutes=end),
    )

    assert result is overlaps


@pytest.mark.parametrize("status", [RequestStatus.PENDING, RequestStatus.ACCEPTED])
async def test_both_active_statuses_block_overlap(
    session: AsyncSession, status: RequestStatus
) -> None:
    trip = await add_trip(session)
    request = make_request(trip, status=status)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    assert await repository.has_overlapping_active_request(
        request.rider_id, DEPARTURE, DEPARTURE + timedelta(minutes=10)
    )


@pytest.mark.parametrize(
    "inactive",
    [
        RequestStatus.DECLINED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
        RequestStatus.PAYMENT_FAILED,
    ],
)
async def test_inactive_requests_do_not_block_overlap(
    session: AsyncSession, inactive: RequestStatus
) -> None:
    trip = await add_trip(session)
    request = make_request(trip, status=inactive)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)

    assert not await repository.has_overlapping_active_request(
        request.rider_id, DEPARTURE, DEPARTURE + timedelta(minutes=10)
    )


async def test_another_riders_request_does_not_block_overlap(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(make_request(trip))

    assert not await repository.has_overlapping_active_request(
        uuid4(), DEPARTURE, DEPARTURE + timedelta(minutes=10)
    )


@pytest.mark.parametrize("status", [TripStatus.CANCELLED, TripStatus.COMPLETED])
async def test_closed_trips_do_not_block_overlap(session: AsyncSession, status: TripStatus) -> None:
    trip = await add_trip(session)
    request = make_request(trip)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)
    await session.execute(update(trips).where(trips.c.id == trip.id).values(status=status.value))

    assert not await repository.has_overlapping_active_request(
        request.rider_id, DEPARTURE, DEPARTURE + timedelta(minutes=10)
    )


async def test_accepted_pickups_are_listed_oldest_first(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)
    first = replace(
        make_request(trip, status=RequestStatus.ACCEPTED, now=datetime(2029, 12, 30, tzinfo=UTC)),
        pickup=Location("First stop", 49.81, -97.14),
    )
    second = replace(
        make_request(trip, status=RequestStatus.ACCEPTED, now=datetime(2029, 12, 31, tzinfo=UTC)),
        pickup=Location("Second stop", 49.82, -97.15),
    )
    pending = make_request(trip)
    for request in (second, pending, first):
        await repository.add(request)

    pickups = await repository.list_accepted_pickups(trip.id)

    assert [pickup.label for pickup in pickups] == ["First stop", "Second stop"]


async def seats_left(session: AsyncSession, trip: Trip) -> int | None:
    return await session.scalar(select(trips.c.seats_available).where(trips.c.id == trip.id))


async def test_seats_can_be_taken_until_none_are_left(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)

    results = [await repository.take_seat(trip.id) for _ in range(4)]

    assert results == [True, True, True, False]
    assert await seats_left(session, trip) == 0


async def test_a_seat_cannot_be_taken_on_a_cancelled_trip(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)
    await session.execute(
        update(trips).where(trips.c.id == trip.id).values(status=TripStatus.CANCELLED.value)
    )

    assert await repository.take_seat(trip.id) is False
    assert await seats_left(session, trip) == 3


async def test_a_released_seat_comes_back(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.take_seat(trip.id)

    await repository.release_seat(trip.id)

    assert await seats_left(session, trip) == 3


async def test_releasing_never_goes_past_the_seat_total(session: AsyncSession) -> None:
    trip = await add_trip(session)
    repository = SQLAlchemySeatRequestRepository(session)

    await repository.release_seat(trip.id)

    assert await seats_left(session, trip) == 3


async def test_a_decision_is_saved_only_while_the_status_matches(session: AsyncSession) -> None:
    trip = await add_trip(session)
    request = make_request(trip)
    repository = SQLAlchemySeatRequestRepository(session)
    await repository.add(request)
    accepted = request.accept(datetime(2029, 12, 31, 12, tzinfo=UTC))

    first = await repository.save_decision(accepted, expected=RequestStatus.PENDING)
    second = await repository.save_decision(accepted, expected=RequestStatus.PENDING)

    assert (first, second) == (True, False)
    assert await repository.get(request.id) == accepted
