"""Exercise both My Trips endpoints against the migrated database."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import (
    RiderTripsQuery,
    UpcomingTripsCommand,
    get_rider_trips,
    get_upcoming_trips,
)
from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.seat_request_repository import SQLAlchemySeatRequestRepository
from trips.domain.entities import Trip
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote, TripStatus
from trips.infrastructure.main import create_app

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)


def make_trip(
    driver_id: UUID,
    departure_minutes: int,
    status: TripStatus,
    direction: Direction = Direction.TO_CAMPUS,
) -> Trip:
    trip = Trip.create(
        driver_id=driver_id,
        direction=direction,
        place=Location("Private driver location", 49.82, -97.15),
        departure_at=NOW + timedelta(minutes=departure_minutes),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    return replace(trip, status=status, seats_available=2)


def make_request(trip: Trip, rider_id: UUID, status: RequestStatus) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=rider_id,
        pickup=Location("Saved pickup", 49.815, -97.14),
        walk_seconds=123,
        rider_distance_meters=4000,
        detour_seconds=180,
        cost=Quote(234, "CAD", "Saved quote"),
        now=NOW - timedelta(days=2),
    )
    return replace(
        request, status=status, decided_at=None if status is RequestStatus.PENDING else NOW
    )


async def test_driver_and_rider_my_trips_time_buckets(trips_database: str) -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    driver = auth.user_id
    rider, other_rider, other_driver = uuid4(), uuid4(), uuid4()
    underway = make_trip(driver, -25, TripStatus.IN_PROGRESS)
    assert underway.estimated_arrival_at < NOW
    departing_now = make_trip(driver, 0, TripStatus.SCHEDULED)
    boundary = make_trip(driver, -15, TripStatus.SCHEDULED)
    cancelled_tomorrow = make_trip(driver, 1440, TripStatus.CANCELLED, Direction.FROM_CAMPUS)
    cancelled_yesterday = make_trip(driver, -1440, TripStatus.CANCELLED)
    completed_early = make_trip(driver, 5, TripStatus.COMPLETED)
    tied = make_trip(driver, 1440, TripStatus.SCHEDULED)
    somebody_elses_trip = make_trip(other_driver, 10, TripStatus.SCHEDULED)

    pending = make_request(underway, rider, RequestStatus.PENDING)
    cancelled = make_request(cancelled_tomorrow, rider, RequestStatus.CANCELLED)
    declined = make_request(cancelled_tomorrow, rider, RequestStatus.DECLINED)
    accepted = make_request(completed_early, rider, RequestStatus.ACCEPTED)
    expired = make_request(boundary, rider, RequestStatus.EXPIRED)
    failed = make_request(cancelled_yesterday, rider, RequestStatus.PAYMENT_FAILED)
    foreign = make_request(underway, other_rider, RequestStatus.ACCEPTED)

    engine = create_async_engine(trips_database)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                sessions = async_sessionmaker(connection)
                async with sessions() as session:
                    trip_repo = SQLAlchemyTripRepository(session)
                    for trip in (
                        tied,
                        cancelled_yesterday,
                        somebody_elses_trip,
                        completed_early,
                        cancelled_tomorrow,
                        boundary,
                        departing_now,
                        underway,
                    ):
                        await trip_repo.add(trip)
                    request_repo = SQLAlchemySeatRequestRepository(session)
                    for request in (
                        failed,
                        declined,
                        foreign,
                        expired,
                        pending,
                        accepted,
                        cancelled,
                    ):
                        await request_repo.add(request)
                    await session.commit()

                app.dependency_overrides[get_upcoming_trips] = lambda: UpcomingTripsCommand(
                    sessions, clock=lambda: NOW
                )
                app.dependency_overrides[get_rider_trips] = lambda: RiderTripsQuery(
                    sessions, clock=lambda: NOW
                )
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    driver_upcoming = await client.get("/mine", headers=auth.headers())
                    driver_past = await client.get("/mine?when=past", headers=auth.headers())
                    rider_headers = auth.headers(user_id=rider)
                    rider_upcoming = await client.get("/requests/mine", headers=rider_headers)
                    rider_past = await client.get("/requests/mine?when=past", headers=rider_headers)
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()

    for response in (driver_upcoming, driver_past, rider_upcoming, rider_past):
        assert response.status_code == 200, response.text

    assert [item["id"] for item in driver_upcoming.json()] == [
        str(underway.id),
        str(departing_now.id),
        *sorted(map(str, (tied.id, cancelled_tomorrow.id))),
    ]
    assert [item["id"] for item in driver_past.json()] == [
        str(completed_early.id),
        str(boundary.id),
        str(cancelled_yesterday.id),
    ]
    for item in [*driver_upcoming.json(), *driver_past.json()]:
        assert item["driverId"] == str(driver)
        assert (item["seatsTotal"], item["seatsAvailable"]) == (3, 2)
        assert "seatsFilled" not in item

    same_trip = sorted((cancelled, declined), key=lambda request: request.id)
    for response, expected in (
        (rider_upcoming, [pending, *same_trip]),
        (rider_past, [accepted, expired, failed]),
    ):
        assert [item["request"]["id"] for item in response.json()] == [
            str(request.id) for request in expected
        ]
        for item, request in zip(response.json(), expected, strict=True):
            assert item["request"]["status"] == request.status.value
            assert item["request"]["riderId"] == str(rider)
            assert item["trip"]["id"] == str(request.trip_id)
            assert item["request"]["pickup"] == {
                "label": "Saved pickup",
                "lat": 49.815,
                "lng": -97.14,
                "walkSeconds": 123,
            }
            assert item["request"]["cost"] == {
                "amountCents": 234,
                "currency": "CAD",
                "explanation": "Saved quote",
            }
            private_end = "origin" if item["trip"]["direction"] == "to_campus" else "destination"
            assert item["trip"][private_end] is None

    cancelled_ids = {str(cancelled_tomorrow.id), str(cancelled_yesterday.id)}
    for upcoming, past, get_trip in (
        (driver_upcoming, driver_past, lambda item: item),
        (rider_upcoming, rider_past, lambda item: item["trip"]),
    ):
        assert {
            get_trip(item)["id"]
            for item in [*upcoming.json(), *past.json()]
            if get_trip(item)["status"] == "cancelled"
        } == cancelled_ids
