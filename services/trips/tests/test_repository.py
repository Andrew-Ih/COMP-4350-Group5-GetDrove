"""Integration tests for the Trips repository."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.adapters.persistence.tables import trips
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location
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
