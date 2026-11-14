"""Integration tests for recurring trip series persistence."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trips.adapters.persistence.repository import (
    SQLAlchemyTripRepository,
    SQLAlchemyTripSeriesRepository,
)
from trips.domain.entities import Trip, TripSeries
from trips.domain.values import Direction, Location
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")


@pytest.mark.asyncio
async def test_save_and_retrieve_trip_series() -> None:
    engine = create_async_engine(get_settings().database_url)

    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        departure = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)

        series = TripSeries.create(
            driver_id=uuid4(),
            direction=Direction.TO_CAMPUS,
            place=Location("Pembina Highway", 49.82, -97.15),
            departure_at=departure,
            seats_total=3,
            weekdays=("mon", "wed", "fri"),
            end_date=(departure + timedelta(weeks=8)).date(),
        )

        async with session_factory() as session:
            repository = SQLAlchemyTripSeriesRepository(session)

            await repository.add(series)
            await session.flush()

            saved = await repository.get_by_id(series.id)

            assert saved is not None
            assert saved.id == series.id
            assert saved.driver_id == series.driver_id
            assert saved.direction == series.direction
            assert saved.place == series.place
            assert saved.departure_at == series.departure_at
            assert saved.seats_total == 3
            assert saved.weekdays == ("mon", "wed", "fri")
            assert saved.end_date == series.end_date
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_trip_can_reference_recurring_series() -> None:
    engine = create_async_engine(get_settings().database_url)

    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        driver_id = uuid4()
        departure = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
        place = Location("Pembina Highway", 49.82, -97.15)

        series = TripSeries.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=departure,
            seats_total=3,
            weekdays=("mon", "wed"),
            end_date=(departure + timedelta(weeks=4)).date(),
        )

        trip = Trip.create(
            driver_id=driver_id,
            direction=Direction.TO_CAMPUS,
            place=place,
            departure_at=departure,
            duration_seconds=900,
            distance_meters=6000,
            seats_total=3,
            series_id=series.id,
        )

        async with session_factory() as session:
            series_repository = SQLAlchemyTripSeriesRepository(session)
            trip_repository = SQLAlchemyTripRepository(session)

            await series_repository.add(series)
            await trip_repository.add(trip)
            await session.flush()

            retrieved = await trip_repository.get_upcoming_by_driver(
                driver_id=driver_id,
                now=departure - timedelta(days=1),
            )

            assert len(retrieved) == 1
            assert retrieved[0].id == trip.id
            assert retrieved[0].series_id == series.id
    finally:
        await engine.dispose()
