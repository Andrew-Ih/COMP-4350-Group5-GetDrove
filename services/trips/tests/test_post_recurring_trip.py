"""Unit tests for posting recurring trips."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from trips.application.ports import RouteEstimate
from trips.application.post_recurring_trip import PostRecurringTrip
from trips.domain.entities import WINNIPEG_TZ, Trip, TripSeries
from trips.domain.errors import DepartureInPastError, DriverNotApprovedError
from trips.domain.recurrence import expand_trip_series
from trips.domain.values import Direction, Location

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
PLACE = Location("Pembina Highway", 49.82, -97.15)


class FakeTripRepository:
    def __init__(self, existing: list[Trip] | None = None) -> None:
        self.existing = existing or []
        self.saved: list[Trip] = []

    async def add(self, trip: Trip) -> None:
        self.saved.append(trip)

    async def get_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]:
        return [
            trip
            for trip in self.existing
            if trip.driver_id == driver_id and trip.departure_at > now
        ]

    async def get_active_or_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]:
        return [
            trip
            for trip in self.existing + self.saved
            if trip.driver_id == driver_id and trip.estimated_arrival_at > now
        ]


class FakeSeriesRepository:
    def __init__(self) -> None:
        self.saved: list[TripSeries] = []

    async def add(self, series: TripSeries) -> None:
        self.saved.append(series)


class FakeEvents:
    def __init__(self) -> None:
        self.posted: list[UUID] = []

    async def trip_posted(self, trip_id: UUID) -> None:
        self.posted.append(trip_id)


class FakeRouting:
    def __init__(self) -> None:
        self.trip_ids: list[UUID] = []
        self.owners: list[tuple[UUID, Direction]] = []

    async def compute_route(
        self,
        trip_id: UUID,
        origin: Location,
        destination: Location,
        driver_id: UUID,
        direction: Direction,
    ) -> RouteEstimate:
        self.trip_ids.append(trip_id)
        self.owners.append((driver_id, direction))
        return RouteEstimate(
            distance_meters=6000,
            duration_seconds=1800,
        )


def make_series(
    driver_id: UUID | None = None,
    departure_at: datetime | None = None,
) -> TripSeries:
    return TripSeries.create(
        driver_id=driver_id or uuid4(),
        direction=Direction.TO_CAMPUS,
        place=PLACE,
        departure_at=departure_at or datetime(2026, 11, 16, 8, tzinfo=WINNIPEG_TZ),
        seats_total=3,
        weekdays=["mon", "wed", "fri"],
        end_date=date(2026, 11, 27),
    )


class FakeApprovedDrivers:
    def __init__(self, approved: bool) -> None:
        self.approved = approved

    async def is_approved(self, driver_id: UUID) -> bool:
        return self.approved


def setup_use_case(
    existing: list[Trip] | None = None,
    approved: bool = True,
):
    trips = FakeTripRepository(existing)
    series_repo = FakeSeriesRepository()
    routing = FakeRouting()
    events = FakeEvents()

    use_case = PostRecurringTrip(
        trip_repository=trips,
        series_repository=series_repo,
        routing=routing,
        events=events,
        approved_drivers=FakeApprovedDrivers(approved),
        clock=lambda: NOW,
    )

    return use_case, trips, series_repo, routing, events


async def test_creates_recurring_trips() -> None:
    use_case, trips, series_repo, routing, events = setup_use_case()
    series = make_series()

    result = await use_case.execute(series, await use_case.prepare(series))

    assert len(result.created_trips) == 6
    assert len(result.skipped_departures) == 0

    assert series_repo.saved == [series]
    assert trips.saved == result.created_trips

    assert routing.trip_ids == [trip.id for trip in result.created_trips]
    # Routing stores each route with its driver and direction, so only the driver sees
    # their own end of it (#135).
    assert routing.owners == [(series.driver_id, series.direction)] * 6

    assert all(trip.series_id == series.id for trip in result.created_trips)

    assert events.posted == [trip.id for trip in result.created_trips]


async def test_routes_at_most_eight_occurrences_and_keeps_departure_order() -> None:
    use_case, _, _, routing, _ = setup_use_case()
    series = replace(make_series(), end_date=date(2026, 12, 11))
    started: list[UUID] = []
    finished: list[UUID] = []
    batch_started = asyncio.Event()
    later_finished = asyncio.Event()
    peak = 0

    async def compute(trip_id: UUID, **_: object) -> RouteEstimate:
        nonlocal peak
        started.append(trip_id)
        peak = max(peak, len(started) - len(finished))
        if len(started) == 8:
            batch_started.set()
        await batch_started.wait()
        await asyncio.sleep(0)
        if trip_id == started[0]:
            await later_finished.wait()
        finished.append(trip_id)
        later_finished.set()
        return RouteEstimate(distance_meters=6000, duration_seconds=1800)

    routing.compute_route = AsyncMock(side_effect=compute)
    async with asyncio.timeout(5):
        candidates = await use_case.prepare(series)

    assert len(candidates) > 8
    assert peak == 8
    assert finished[0] != started[0]
    assert [trip.id for trip in candidates] == started
    assert [trip.departure_at for trip in candidates] == expand_trip_series(series)


async def test_skips_overlapping_departure() -> None:
    series = make_series()

    # Existing trip overlaps Monday's 8:00-8:30 occurrence.
    existing = Trip.create(
        driver_id=series.driver_id,
        direction=Direction.TO_CAMPUS,
        place=PLACE,
        departure_at=datetime(2026, 11, 16, 8, 15, tzinfo=WINNIPEG_TZ),
        duration_seconds=1800,
        distance_meters=6000,
        seats_total=3,
    )

    use_case, trips, _, routing, events = setup_use_case(existing=[existing])

    candidates = await use_case.prepare(series)
    result = await use_case.execute(series, candidates)

    assert len(result.created_trips) == 5
    assert len(result.skipped_departures) == 1

    assert result.skipped_departures[0].astimezone(WINNIPEG_TZ).date() == date(2026, 11, 16)

    assert len(trips.saved) == 5
    assert len(events.posted) == 5
    assert routing.trip_ids == [trip.id for trip in candidates]


async def test_allows_adjacent_trip() -> None:
    series = make_series()

    # Existing trip ends exactly when the recurring trip starts.
    existing = Trip.create(
        driver_id=series.driver_id,
        direction=Direction.TO_CAMPUS,
        place=PLACE,
        departure_at=datetime(2026, 11, 16, 7, 30, tzinfo=WINNIPEG_TZ),
        duration_seconds=1800,
        distance_meters=6000,
        seats_total=3,
    )

    use_case, _, _, _, _ = setup_use_case([existing])

    result = await use_case.execute(series, await use_case.prepare(series))

    assert len(result.created_trips) == 6
    assert result.skipped_departures == []


async def test_preserves_trip_duration() -> None:
    use_case, _, _, _, _ = setup_use_case()

    series = make_series()
    result = await use_case.execute(series, await use_case.prepare(series))

    for trip in result.created_trips:
        assert trip.estimated_arrival_at - trip.departure_at == timedelta(minutes=30)


async def test_rejects_past_departure() -> None:
    use_case, trips, series_repo, routing, events = setup_use_case()

    series = make_series(departure_at=datetime(2026, 11, 13, 8, tzinfo=WINNIPEG_TZ))

    with pytest.raises(DepartureInPastError):
        await use_case.prepare(series)

    assert trips.saved == []
    assert series_repo.saved == []
    assert routing.trip_ids == []
    assert events.posted == []


async def test_an_unapproved_driver_cant_post_a_series() -> None:
    """#8, #11: refused before any route is worked out, and nothing is saved."""
    use_case, trips, series_repo, routing, events = setup_use_case(approved=False)

    with pytest.raises(DriverNotApprovedError):
        await use_case.prepare(make_series())

    assert routing.trip_ids == []
    assert trips.saved == []
    assert series_repo.saved == []
    assert events.posted == []
