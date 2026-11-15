import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import CancelTripCommand, get_cancel_trip
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import outbox, seat_requests, trips
from trips.application.cancel_trip import CancelTrip
from trips.domain.entities import Trip
from trips.domain.errors import TripNotCancellableError
from trips.domain.values import Direction, Location, SearchWindow, TripStatus
from trips.infrastructure.main import create_app

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)


def make_trip(driver_id, departure_at):
    return Trip.create(
        driver_id,
        Direction.FROM_CAMPUS,
        Location("Home", 49.82, -97.15),
        departure_at,
        900,
        6000,
        3,
    )


@pytest.mark.parametrize(
    ("minutes", "status", "owner", "expected", "code"),
    [
        (59, TripStatus.SCHEDULED, True, 200, None),
        (60, TripStatus.SCHEDULED, True, 200, None),
        (0, TripStatus.SCHEDULED, True, 409, "trip_not_cancellable"),
        (-1, TripStatus.SCHEDULED, True, 409, "trip_not_cancellable"),
        (30, TripStatus.IN_PROGRESS, True, 409, "trip_not_cancellable"),
        (30, TripStatus.COMPLETED, True, 409, "trip_not_cancellable"),
        (30, TripStatus.CANCELLED, True, 409, "trip_not_cancellable"),
        (30, TripStatus.SCHEDULED, False, 403, "not_trip_driver"),
        (30, None, True, 404, "trip_not_found"),
    ],
)
async def test_cancel_trip(minutes, status, owner, expected, code):
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    trip = make_trip(auth.user_id if owner else uuid4(), NOW + timedelta(minutes=minutes))
    if status is not None:
        trip.status = status
    riders = [uuid4(), uuid4()]
    repository = AsyncMock()
    repository.get_for_update.return_value = trip if status is not None else None
    repository.save_cancellation.return_value = riders
    events = AsyncMock()
    use_case = CancelTrip(repository, events, clock=lambda: NOW)
    app.dependency_overrides[get_cancel_trip] = lambda: use_case

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/{trip.id}/cancel", headers=auth.headers())

    assert response.status_code == expected, response.text
    repository.get_for_update.assert_awaited_once_with(trip.id)
    if expected == 200:
        assert response.json()["status"] == "cancelled"
        repository.save_cancellation.assert_awaited_once_with(trip, NOW)
        events.trip_cancelled.assert_awaited_once_with(trip, riders)
        if minutes < 60:
            events.driver_late_cancellation.assert_awaited_once_with(trip, NOW)
        else:
            events.driver_late_cancellation.assert_not_awaited()
    else:
        assert response.json()["code"] == code
        repository.save_cancellation.assert_not_awaited()
        assert not events.mock_calls


async def test_cancellation_closes_requests_and_records_events_once(trips_database):
    engine = create_async_engine(trips_database)
    sessions = async_sessionmaker(engine)
    now = datetime.now(UTC)
    trip = make_trip(uuid4(), now + timedelta(minutes=30))
    pending, accepted, declined = uuid4(), uuid4(), uuid4()
    trip_events = outbox.c.envelope["payload"]["tripId"].astext == str(trip.id)

    try:
        async with sessions.begin() as session:
            await SQLAlchemyTripRepository(session).add(trip)
            await session.execute(
                insert(seat_requests),
                [
                    {
                        "id": uuid4(),
                        "trip_id": trip.id,
                        "rider_id": rider,
                        "status": status,
                        "pickup_label": "Campus",
                        "pickup_lat": 49.8,
                        "pickup_lng": -97.1,
                        "walk_seconds": 60,
                        "rider_distance_meters": 5000,
                        "amount_cents": 300,
                        "currency": "CAD",
                        "cost_explanation": "Saved fare",
                    }
                    for rider, status in (
                        (pending, "pending"),
                        (accepted, "accepted"),
                        (declined, "declined"),
                    )
                ],
            )

        command = CancelTripCommand(sessions)
        outcomes = await asyncio.gather(
            command.execute(trip_id=trip.id, driver_id=trip.driver_id),
            command.execute(trip_id=trip.id, driver_id=trip.driver_id),
            return_exceptions=True,
        )
        assert sum(isinstance(result, Trip) for result in outcomes) == 1
        assert sum(isinstance(result, TripNotCancellableError) for result in outcomes) == 1

        async with sessions() as session:
            repository = SQLAlchemyTripRepository(session)
            mine = await repository.get_upcoming_by_driver(trip.driver_id, now)
            assert [item.status for item in mine] == [TripStatus.CANCELLED]
            window = SearchWindow.for_rider(trip.direction, now)
            assert trip.id not in {
                item.id for item in await repository.search(window, now, pending)
            }

            requests = await session.execute(
                select(seat_requests).where(seat_requests.c.trip_id == trip.id)
            )
            rows = {row.rider_id: row for row in requests}
            assert rows[pending].status == rows[accepted].status == "cancelled"
            assert rows[pending].decided_at == rows[accepted].decided_at
            assert rows[declined].status == "declined"

            events = await session.scalars(
                select(outbox.c.envelope).where(trip_events).order_by(outbox.c.id)
            )
            cancellation, late = events.all()
            assert cancellation["type"] == "TripCancelled"
            assert set(cancellation["payload"]["riderIds"]) == {str(pending), str(accepted)}
            assert late["type"] == "DriverLateCancellation"
    finally:
        # Both commands use independent transactions, so their committed rows need cleanup.
        try:
            async with sessions.begin() as session:
                await session.execute(delete(outbox).where(trip_events))
                await session.execute(
                    delete(seat_requests).where(seat_requests.c.trip_id == trip.id)
                )
                await session.execute(delete(trips).where(trips.c.id == trip.id))
        finally:
            await engine.dispose()
