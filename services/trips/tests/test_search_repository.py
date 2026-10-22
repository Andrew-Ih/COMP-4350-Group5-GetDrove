"""Integration tests for the Trips repository's search (#97, real PostgreSQL)."""

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from trips.adapters.persistence.repository import SQLAlchemyTripRepository
from trips.domain.entities import Trip
from trips.domain.values import Direction, Location, SearchWindow, TripStatus
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")

# Well in the future, so other trips in a local database don't get in the way.
TIME = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
NOW = datetime.now(UTC)
RIDER_ID = uuid4()


@pytest.fixture
async def repository() -> AsyncIterator[SQLAlchemyTripRepository]:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with AsyncSession(engine) as session:
            yield SQLAlchemyTripRepository(session)
            # No commit: closing the session rolls back test data.
    finally:
        await engine.dispose()


def trip(
    departure: datetime,
    direction: Direction = Direction.TO_CAMPUS,
    duration_minutes: int = 15,
    driver_id: UUID | None = None,
) -> Trip:
    return Trip.create(
        driver_id=driver_id or uuid4(),
        direction=direction,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=departure,
        duration_seconds=duration_minutes * 60,
        distance_meters=6000,
        seats_total=3,
    )


async def found(
    repository: SQLAlchemyTripRepository, direction: Direction, *mine: Trip
) -> list[UUID]:
    """The search's results, among the trips this test added."""
    for t in mine:
        await repository.add(t)
    results = await repository.search(
        SearchWindow.for_rider(direction, TIME), departs_after=NOW, exclude_driver_id=RIDER_ID
    )
    ids = {t.id for t in mine}
    return [t.id for t in results if t.id in ids]


async def test_to_campus_matches_trips_arriving_in_the_hour_before(
    repository: SQLAlchemyTripRepository,
) -> None:
    # Arrivals (departure + 15 min): 30 min before, exactly an hour before, exactly on time,
    # 61 min before, and 5 min after.
    inside = trip(TIME - timedelta(minutes=45))
    at_start = trip(TIME - timedelta(minutes=75))
    at_end = trip(TIME - timedelta(minutes=15))
    too_early = trip(TIME - timedelta(minutes=76))
    too_late = trip(TIME - timedelta(minutes=10))

    ids = await found(
        repository, Direction.TO_CAMPUS, inside, at_start, at_end, too_early, too_late
    )

    assert set(ids) == {inside.id, at_start.id, at_end.id}


async def test_from_campus_matches_trips_leaving_in_the_hour_after(
    repository: SQLAlchemyTripRepository,
) -> None:
    inside = trip(TIME + timedelta(minutes=30), Direction.FROM_CAMPUS)
    at_start = trip(TIME, Direction.FROM_CAMPUS)
    at_end = trip(TIME + timedelta(hours=1), Direction.FROM_CAMPUS)
    before = trip(TIME - timedelta(minutes=1), Direction.FROM_CAMPUS)
    after = trip(TIME + timedelta(minutes=61), Direction.FROM_CAMPUS)

    ids = await found(repository, Direction.FROM_CAMPUS, inside, at_start, at_end, before, after)

    assert set(ids) == {inside.id, at_start.id, at_end.id}


async def test_only_trips_in_the_riders_direction(repository: SQLAlchemyTripRepository) -> None:
    to_campus = trip(TIME - timedelta(minutes=45))
    from_campus = trip(TIME - timedelta(minutes=45), Direction.FROM_CAMPUS)

    assert await found(repository, Direction.TO_CAMPUS, to_campus, from_campus) == [to_campus.id]


async def test_full_cancelled_and_own_trips_are_left_out(
    repository: SQLAlchemyTripRepository,
) -> None:
    departure = TIME - timedelta(minutes=45)
    open_trip = trip(departure)
    full = replace(trip(departure), seats_available=0)
    cancelled = replace(trip(departure), status=TripStatus.CANCELLED)
    started = replace(trip(departure), status=TripStatus.IN_PROGRESS)
    own = trip(departure, driver_id=RIDER_ID)

    ids = await found(repository, Direction.TO_CAMPUS, open_trip, full, cancelled, started, own)

    assert ids == [open_trip.id]


async def test_trips_that_already_left_are_left_out(
    repository: SQLAlchemyTripRepository,
) -> None:
    """A rider searching now for a trip "arriving by" soon mustn't see one already on its way."""
    departed = trip(datetime.now(UTC) - timedelta(minutes=5), duration_minutes=60)
    upcoming = trip(datetime.now(UTC) + timedelta(minutes=5), duration_minutes=40)
    for t in (departed, upcoming):
        await repository.add(t)

    results = await repository.search(
        SearchWindow.for_rider(Direction.TO_CAMPUS, datetime.now(UTC) + timedelta(hours=1)),
        departs_after=datetime.now(UTC),
        exclude_driver_id=RIDER_ID,
    )

    ids = [t.id for t in results]
    assert upcoming.id in ids
    assert departed.id not in ids


async def test_results_are_whole_trips_soonest_first(
    repository: SQLAlchemyTripRepository,
) -> None:
    later = trip(TIME - timedelta(minutes=30))
    sooner = trip(TIME - timedelta(minutes=50))
    for t in (later, sooner):
        await repository.add(t)

    results = await repository.search(
        SearchWindow.for_rider(Direction.TO_CAMPUS, TIME),
        departs_after=NOW,
        exclude_driver_id=RIDER_ID,
    )

    mine = [t for t in results if t.id in {later.id, sooner.id}]
    # Read back exactly as written: the same domain entities.
    assert mine == [sooner, later]
