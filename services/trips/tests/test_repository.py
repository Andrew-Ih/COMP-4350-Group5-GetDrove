"""Integration tests for the Trips repository."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, TripStatus
from trips.infrastructure.settings import get_settings


@pytest.mark.asyncio
async def test_add_trip_saves_to_database() -> None:
    engine = create_async_engine(get_settings().database_url)

    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        trip = Trip.create(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=Location(
                label="Pembina Highway",
                lat=49.82,
                lng=-97.15,
            ),
            departure_at=datetime(2026, 10, 20, 8, 0, tzinfo=UTC),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )

        async with session_factory() as session:
            repository = SQLAlchemyTripRepository(session)

            await repository.add(trip)
            await session.flush()

            result = await session.execute(select(trips).where(trips.c.id == trip.id))
            saved_trip = result.mappings().one()

            assert saved_trip["id"] == trip.id
            assert saved_trip["driver_id"] == trip.driver_id
            assert saved_trip["direction"] == "to_campus"
            assert saved_trip["seats_available"] == 3

            # No commit: closing the session rolls back test data.
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_upcoming_by_driver_filters_and_sorts_trips() -> None:
    engine = create_async_engine(get_settings().database_url)

    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        driver_id = uuid4()
        other_driver_id = uuid4()
        now = datetime.now(UTC)

        place = Location(
            label="Pembina Highway",
            lat=49.82,
            lng=-97.15,
        )

        # Insert in an order that differs from the expected result.
        later_trip = Trip.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=now + timedelta(days=3),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )

        earlier_trip = Trip.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=now + timedelta(days=1),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )

        past_trip = Trip.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=now - timedelta(days=1),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )

        other_driver_trip = Trip.create(
            driver_id=other_driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=now + timedelta(days=2),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
        )

        cancelled_trip = Trip.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=now - timedelta(days=2),
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
            status=TripStatus.CANCELLED,
        )

        # cancelled_trip.status = replace(cancelled_trip.status, value=TripStatus.CANCELLED)

        async with session_factory() as session:
            repository = SQLAlchemyTripRepository(session)

            for trip in (
                later_trip,
                past_trip,
                other_driver_trip,
                cancelled_trip,
                earlier_trip,
            ):
                await repository.add(trip)

            await session.flush()

            result = await repository.get_upcoming_by_driver(
                driver_id=driver_id,
                now=now,
            )

            assert [trip.id for trip in result] == [
                earlier_trip.id,
                later_trip.id,
            ]

            # No commit: closing the session rolls back test data.
    finally:
        await engine.dispose()
