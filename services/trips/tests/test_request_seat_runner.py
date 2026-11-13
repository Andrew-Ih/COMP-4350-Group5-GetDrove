"""The seat-request runner turns a unique-index violation into already_requested."""

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import delete

from trips.adapters.persistence.tables import seat_requests, trips
from trips.adapters.api.dependencies import RequestSeatRunner
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import (
    SQLAlchemySeatRequestRepository,
)
from trips.application.request_seat import RequestSeat
from trips.domain.entities import Trip
from trips.domain.request_errors import AlreadyRequestedError
from trips.domain.seat_request import SeatRequest
from trips.domain.values import Direction, Location, Quote

pytestmark = pytest.mark.usefixtures("trips_database")

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)


def make_trip() -> Trip:
    return Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=DEPARTURE,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )


def make_request(trip: Trip, rider_id: UUID) -> SeatRequest:
    return SeatRequest.create(
        trip_id=trip.id,
        rider_id=rider_id,
        pickup=Location("Pickup point", 49.815, -97.14),
        walk_seconds=120,
        rider_distance_meters=4000,
        detour_seconds=180,
        cost=Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)"),
        now=datetime(2029, 12, 31, tzinfo=UTC),
    )


async def test_unique_index_violation_becomes_already_requested(monkeypatch) -> None:
    engine = create_async_engine(os.environ["TRIPS_DATABASE_URL"])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    trip = make_trip()
    rider_id = uuid4()

    # An active request for this rider and trip is already saved.
    async with session_factory() as session, session.begin():
        await SQLAlchemyTripRepository(session).add(trip)
        await SQLAlchemySeatRequestRepository(session).add(make_request(trip, rider_id))

    # Skip the "already requested?" pre-check and insert a second active request,
    # so the database's unique index is what rejects it.
    async def insert_duplicate(self, command):
        await self.requests.add(make_request(trip, rider_id))

    monkeypatch.setattr(RequestSeat, "execute", insert_duplicate)

    runner = RequestSeatRunner(
        session_factory=session_factory,
        routing=None,  # type: ignore[arg-type]
        pricing=None,  # type: ignore[arg-type]
        cards=None,  # type: ignore[arg-type]
    )

    try:
        with pytest.raises(AlreadyRequestedError):
            await runner.execute(None)  # type: ignore[arg-type]
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(delete(seat_requests).where(seat_requests.c.trip_id == trip.id))
            await session.execute(delete(trips).where(trips.c.id == trip.id))
        await engine.dispose()
