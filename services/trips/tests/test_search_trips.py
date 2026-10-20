"""Unit tests for searching trips (#97): the time window and the SearchTrips use case."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from trips.application.search_trips import SearchTrips
from trips.domain.entities import Trip
from trips.domain.errors import PricingUnavailableError, RoutingUnavailableError
from trips.domain.values import (
    Direction,
    Location,
    Point,
    Quote,
    SearchWindow,
    TripMatch,
    ride_meters,
)

NOW = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
TIME = datetime(2026, 10, 20, 13, 30, tzinfo=UTC)
RIDER = Point(lat=49.85, lng=-97.15)
RIDER_ID = uuid4()


def trip(departure: datetime, direction: Direction = Direction.TO_CAMPUS) -> Trip:
    return Trip.create(
        driver_id=uuid4(),
        direction=direction,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=departure,
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )


def match(trip: Trip, to_end: int = 4000) -> TripMatch:
    """Routing's answer: the pickup is ``to_end`` meters from the end of the trip (6 km)."""
    return TripMatch(
        trip_id=trip.id,
        pickup=Location("Pembina Highway", 49.84, -97.15),
        walk_seconds=240,
        meters_to_trip_end=to_end,
    )


class FakeRepository:
    def __init__(self, *trips: Trip) -> None:
        self.trips = list(trips)
        self.searches: list[tuple[SearchWindow, datetime, UUID]] = []

    async def add(self, trip: Trip) -> None:
        self.trips.append(trip)

    async def search(
        self, window: SearchWindow, departs_after: datetime, exclude_driver_id: UUID
    ) -> list[Trip]:
        self.searches.append((window, departs_after, exclude_driver_id))
        return list(self.trips)


class FakeRouting:
    def __init__(self, matches: list[TripMatch], error: Exception | None = None) -> None:
        self.matches = matches
        self.error = error
        self.calls: list[tuple[Point, list[UUID]]] = []

    async def match(self, rider: Point, trip_ids: Sequence[UUID]) -> list[TripMatch]:
        self.calls.append((rider, list(trip_ids)))
        if self.error:
            raise self.error
        return self.matches


class FakePricing:
    def __init__(self, fail_for: set[int] | None = None) -> None:
        self.fail_for = fail_for or set()
        self.asked: list[int] = []

    async def quote(self, distance_meters: int) -> Quote:
        self.asked.append(distance_meters)
        if distance_meters in self.fail_for:
            raise PricingUnavailableError()
        cents = distance_meters * 45 // 1000
        return Quote(cents, "CAD", f"{distance_meters / 1000:.1f} km at $0.45/km")


def search(
    repository: FakeRepository, routing: FakeRouting, pricing: FakePricing | None = None
) -> SearchTrips:
    return SearchTrips(repository, routing, pricing or FakePricing(), clock=lambda: NOW)


# ---------------------------------------------------------------- the time window


def test_going_to_campus_means_arriving_in_the_hour_before() -> None:
    window = SearchWindow.for_rider(Direction.TO_CAMPUS, TIME)

    assert window == SearchWindow(
        Direction.TO_CAMPUS, TIME - timedelta(hours=1), TIME, by_arrival=True
    )


def test_leaving_campus_means_departing_in_the_hour_after() -> None:
    window = SearchWindow.for_rider(Direction.FROM_CAMPUS, TIME)

    assert window == SearchWindow(
        Direction.FROM_CAMPUS, TIME, TIME + timedelta(hours=1), by_arrival=False
    )


def test_search_time_needs_a_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        SearchWindow.for_rider(Direction.TO_CAMPUS, TIME.replace(tzinfo=None))


# ---------------------------------------------------------------- how far the rider rides


def test_going_to_campus_the_rider_rides_from_the_pickup_to_the_end() -> None:
    to_campus = trip(TIME, Direction.TO_CAMPUS)

    assert ride_meters(Direction.TO_CAMPUS, 6000, match(to_campus, to_end=4000)) == 4000


def test_leaving_campus_the_rider_rides_from_campus_to_the_drop_off() -> None:
    """The point is a drop-off 1.5 km before the driver's end: the rider rides 4.5 km."""
    from_campus = trip(TIME, Direction.FROM_CAMPUS)

    assert ride_meters(Direction.FROM_CAMPUS, 6000, match(from_campus, to_end=1500)) == 4500


def test_ride_is_never_negative() -> None:
    """If Routing's distance ever disagreed with the stored trip, don't price a negative."""
    from_campus = trip(TIME, Direction.FROM_CAMPUS)

    assert ride_meters(Direction.FROM_CAMPUS, 6000, match(from_campus, to_end=6200)) == 0


# ---------------------------------------------------------------- the use case


async def test_returns_matching_trips_with_pickup_and_cost() -> None:
    first = trip(TIME - timedelta(minutes=40))
    repository, routing, pricing = FakeRepository(first), FakeRouting([match(first)]), FakePricing()

    [result] = await search(repository, routing, pricing).execute(
        RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME
    )

    assert result.trip == first
    assert result.match == match(first)
    # Priced on how far the rider rides, not the whole trip.
    assert pricing.asked == [4000]
    assert result.cost == Quote(180, "CAD", "4.0 km at $0.45/km")
    # Trips filters first, then Routing only sees the candidates.
    [(window, departs_after, excluded)] = repository.searches
    assert window == SearchWindow.for_rider(Direction.TO_CAMPUS, TIME)
    assert departs_after == NOW
    assert excluded == RIDER_ID
    assert routing.calls == [(RIDER, [first.id])]


async def test_leaving_campus_prices_the_ride_from_campus_to_the_drop_off() -> None:
    """The bug this guards against: pricing the stretch after the drop-off instead, which
    charged a rider dropped near the end of a 21 km trip for 1.3 km."""
    from_campus = trip(TIME + timedelta(minutes=20), Direction.FROM_CAMPUS)
    pricing = FakePricing()

    [result] = await search(
        FakeRepository(from_campus), FakeRouting([match(from_campus, to_end=1500)]), pricing
    ).execute(RIDER_ID, RIDER, Direction.FROM_CAMPUS, TIME)

    assert pricing.asked == [4500]  # 6000 m trip, dropped off 1500 m before its end
    assert result.cost == Quote(202, "CAD", "4.5 km at $0.45/km")


async def test_trips_the_rider_cant_walk_to_are_left_out() -> None:
    near, far = trip(TIME - timedelta(minutes=40)), trip(TIME - timedelta(minutes=30))

    results = await search(FakeRepository(near, far), FakeRouting([match(near)])).execute(
        RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME
    )

    assert [r.trip for r in results] == [near]


async def test_results_are_sorted_soonest_departure_first() -> None:
    late, early, middle = (trip(TIME - timedelta(minutes=m)) for m in (20, 50, 35))
    routing = FakeRouting([match(late), match(early), match(middle)])

    results = await search(FakeRepository(late, early, middle), routing).execute(
        RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME
    )

    assert [r.trip for r in results] == [early, middle, late]


async def test_no_candidates_means_routing_is_never_asked() -> None:
    routing, pricing = FakeRouting([]), FakePricing()

    results = await search(FakeRepository(), routing, pricing).execute(
        RIDER_ID, RIDER, Direction.FROM_CAMPUS, TIME
    )

    assert results == []
    assert routing.calls == pricing.asked == []


async def test_no_matches_is_an_empty_result() -> None:
    results = await search(FakeRepository(trip(TIME)), FakeRouting([])).execute(
        RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME
    )

    assert results == []


async def test_a_trip_without_a_price_is_still_shown() -> None:
    """Payments being down (or not built yet) must never hide a trip."""
    priced, unpriced = trip(TIME - timedelta(minutes=50)), trip(TIME - timedelta(minutes=30))
    routing = FakeRouting([match(priced, to_end=4000), match(unpriced, to_end=5000)])

    results = await search(
        FakeRepository(priced, unpriced), routing, FakePricing(fail_for={5000})
    ).execute(RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME)

    assert [(r.trip, r.cost is not None) for r in results] == [(priced, True), (unpriced, False)]


async def test_matches_for_trips_that_werent_candidates_are_ignored() -> None:
    candidate = trip(TIME - timedelta(minutes=40))
    stranger = trip(TIME - timedelta(minutes=30))

    results = await search(
        FakeRepository(candidate), FakeRouting([match(stranger), match(candidate)])
    ).execute(RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME)

    assert [r.trip for r in results] == [candidate]


async def test_routing_down_is_an_error() -> None:
    routing = FakeRouting([], error=RoutingUnavailableError())

    with pytest.raises(RoutingUnavailableError):
        await search(FakeRepository(trip(TIME)), routing).execute(
            RIDER_ID, RIDER, Direction.TO_CAMPUS, TIME
        )
