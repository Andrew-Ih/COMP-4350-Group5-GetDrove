"""The driver's request list use case (#139)."""

import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from trips.application.list_trip_requests import ListTripRequests, ListTripRequestsCommand
from trips.application.ports import RiderProfile
from trips.domain.entities import Trip
from trips.domain.request_errors import (
    AccountsUnavailableError,
    NotTripDriverError,
    TripNotFoundError,
)
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote, TripStatus

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2029, 12, 31, tzinfo=UTC)


def make_trip() -> Trip:
    return Trip(
        id=uuid4(),
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        origin=Location("Home", 49.8, -97.2),
        destination=Location("Campus", 49.8075, -97.1366),
        departure_at=DEPARTURE,
        estimated_arrival_at=DEPARTURE.replace(hour=10),
        duration_seconds=3600,
        distance_meters=10000,
        seats_total=3,
        seats_available=3,
        status=TripStatus.SCHEDULED,
    )


def make_request(
    trip: Trip, status: RequestStatus, detour_seconds: int | None = 180
) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=uuid4(),
        pickup=Location("Pembina pickup", 49.82, -97.15),
        walk_seconds=120,
        rider_distance_meters=4000,
        detour_seconds=detour_seconds,
        cost=Quote(450, "CAD", "$4.50 for 10 km"),
        now=NOW,
    )
    return replace(request, status=status)


def profile(rider_id: UUID) -> RiderProfile:
    return RiderProfile(
        id=rider_id, first_name="Priya", rating=4.5, rating_count=8, no_show_count=1
    )


class FakeTrips:
    def __init__(self, trip: Trip | None) -> None:
        self.trip = trip

    async def get(self, trip_id: UUID) -> Trip | None:
        return self.trip


class FakeRequests:
    def __init__(self, requests: list[SeatRequest]) -> None:
        self.requests = requests

    async def list_open_for_trip(self, trip_id: UUID) -> list[SeatRequest]:
        return self.requests


class FakeRiders:
    def __init__(self, *, missing: Sequence[UUID] = (), error: Exception | None = None) -> None:
        self.missing = set(missing)
        self.error = error
        self.calls: list[list[UUID]] = []

    async def get_many(self, rider_ids: Sequence[UUID]) -> dict[UUID, RiderProfile]:
        self.calls.append(list(rider_ids))
        if self.error is not None:
            raise self.error
        return {
            rider_id: profile(rider_id) for rider_id in rider_ids if rider_id not in self.missing
        }


def build(trip: Trip | None, requests: list[SeatRequest], riders: FakeRiders) -> ListTripRequests:
    return ListTripRequests(trips=FakeTrips(trip), requests=FakeRequests(requests), riders=riders)


async def test_driver_sees_every_request_with_rider_details_and_pickup_order() -> None:
    trip = make_trip()
    pending = make_request(trip, RequestStatus.PENDING)
    first = make_request(trip, RequestStatus.ACCEPTED)
    second = make_request(trip, RequestStatus.ACCEPTED)
    riders = FakeRiders()

    items = await build(trip, [pending, first, second], riders).execute(
        ListTripRequestsCommand(trip.id, trip.driver_id)
    )

    assert [item.request.id for item in items] == [pending.id, first.id, second.id]
    assert [item.pickup_order for item in items] == [None, 1, 2]
    assert items[0].rider == profile(pending.rider_id)


async def test_all_riders_are_looked_up_in_one_call() -> None:
    trip = make_trip()
    requests = [make_request(trip, RequestStatus.PENDING) for _ in range(3)]
    riders = FakeRiders()

    await build(trip, requests, riders).execute(ListTripRequestsCommand(trip.id, trip.driver_id))

    assert riders.calls == [[request.rider_id for request in requests]]


async def test_an_unknown_detour_stays_unknown() -> None:
    trip = make_trip()
    request = make_request(trip, RequestStatus.PENDING, detour_seconds=None)

    items = await build(trip, [request], FakeRiders()).execute(
        ListTripRequestsCommand(trip.id, trip.driver_id)
    )

    assert items[0].request.detour_seconds is None


async def test_only_the_trips_driver_can_see_the_list() -> None:
    trip = make_trip()
    riders = FakeRiders()
    use_case = build(trip, [make_request(trip, RequestStatus.PENDING)], riders)

    with pytest.raises(NotTripDriverError):
        await use_case.execute(ListTripRequestsCommand(trip.id, uuid4()))

    assert riders.calls == []


async def test_unknown_trip_is_not_found() -> None:
    with pytest.raises(TripNotFoundError):
        await build(None, [], FakeRiders()).execute(ListTripRequestsCommand(uuid4(), uuid4()))


async def test_a_trip_with_no_requests_does_not_call_accounts() -> None:
    trip = make_trip()
    riders = FakeRiders()

    items = await build(trip, [], riders).execute(ListTripRequestsCommand(trip.id, trip.driver_id))

    assert items == []
    assert riders.calls == []


async def test_accounts_failure_is_reported() -> None:
    trip = make_trip()
    use_case = build(
        trip,
        [make_request(trip, RequestStatus.PENDING)],
        FakeRiders(error=AccountsUnavailableError()),
    )

    with pytest.raises(AccountsUnavailableError):
        await use_case.execute(ListTripRequestsCommand(trip.id, trip.driver_id))


async def test_a_rider_missing_from_accounts_is_skipped_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    trip = make_trip()
    lost = make_request(trip, RequestStatus.PENDING)
    kept = make_request(trip, RequestStatus.PENDING)
    use_case = build(trip, [lost, kept], FakeRiders(missing=[lost.rider_id]))

    with caplog.at_level(logging.WARNING, logger="trips.application.list_trip_requests"):
        items = await use_case.execute(ListTripRequestsCommand(trip.id, trip.driver_id))

    assert [item.request.id for item in items] == [kept.id]
    assert str(lost.id) in caplog.text
    assert "Priya" not in caplog.text


async def test_a_skipped_accepted_rider_still_holds_their_place_in_the_order() -> None:
    trip = make_trip()
    lost = make_request(trip, RequestStatus.ACCEPTED)
    kept = make_request(trip, RequestStatus.ACCEPTED)
    use_case = build(trip, [lost, kept], FakeRiders(missing=[lost.rider_id]))

    items = await use_case.execute(ListTripRequestsCommand(trip.id, trip.driver_id))

    assert [item.pickup_order for item in items] == [2]
