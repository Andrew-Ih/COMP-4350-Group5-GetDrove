"""Accept, decline and cancel use case tests (#138)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from trips.application.decide_request import (
    AcceptRequest,
    CancelRequest,
    DeclineRequest,
    RequestActionCommand,
)
from trips.domain.entities import Trip
from trips.domain.request_errors import (
    NotTripDriverError,
    NotYourRequestError,
    RequestNotCancellableError,
    RequestNotDecidableError,
    RequestNotFoundError,
    RequestNotPendingError,
    SeatTakenError,
)
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Quote, TripStatus

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2029, 12, 31, tzinfo=UTC)
NOT_PENDING = [
    RequestStatus.ACCEPTED,
    RequestStatus.DECLINED,
    RequestStatus.CANCELLED,
    RequestStatus.EXPIRED,
    RequestStatus.PAYMENT_FAILED,
]
FINISHED = [
    RequestStatus.DECLINED,
    RequestStatus.CANCELLED,
    RequestStatus.EXPIRED,
    RequestStatus.PAYMENT_FAILED,
]


def make_trip(*, seats_available: int, status: TripStatus) -> Trip:
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
        seats_available=seats_available,
        status=status,
    )


def make_request(trip: Trip, status: RequestStatus) -> SeatRequest:
    request = SeatRequest.create(
        trip_id=trip.id,
        rider_id=uuid4(),
        pickup=Location("Pembina pickup", 49.82, -97.15),
        walk_seconds=120,
        rider_distance_meters=4000,
        detour_seconds=180,
        cost=Quote(450, "CAD", "$4.50 for 10 km"),
        now=NOW,
    )
    return replace(request, status=status)


class FakeTrips:
    def __init__(self, trip: Trip) -> None:
        self.trip = trip

    async def get(self, trip_id: UUID) -> Trip | None:
        return self.trip if trip_id == self.trip.id else None


class FakeRequests:
    def __init__(self, trip: Trip, request: SeatRequest) -> None:
        self.trip = trip
        self.items = {request.id: request}

    async def get(self, request_id: UUID) -> SeatRequest | None:
        return self.items.get(request_id)

    async def save_decision(self, request: SeatRequest, *, expected: RequestStatus) -> bool:
        if self.items[request.id].status is not expected:
            return False
        self.items[request.id] = request
        return True

    async def take_seat(self, trip_id: UUID) -> bool:
        if self.trip.seats_available == 0:
            return False
        self.trip.seats_available -= 1
        return True

    async def release_seat(self, trip_id: UUID) -> None:
        self.trip.seats_available += 1


class FakeEvents:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID, bool | None]] = []

    async def request_accepted(self, request: SeatRequest, trip: Trip) -> None:
        self.calls.append(("accepted", request.id, None))

    async def request_declined(
        self, request: SeatRequest, trip: Trip, *, was_accepted: bool
    ) -> None:
        self.calls.append(("declined", request.id, was_accepted))

    async def request_cancelled(
        self, request: SeatRequest, trip: Trip, *, was_accepted: bool
    ) -> None:
        self.calls.append(("cancelled", request.id, was_accepted))


class Setup:
    def __init__(
        self,
        *,
        status: RequestStatus = RequestStatus.PENDING,
        seats_available: int = 2,
        trip_status: TripStatus = TripStatus.SCHEDULED,
    ) -> None:
        self.trip = make_trip(seats_available=seats_available, status=trip_status)
        self.request = make_request(self.trip, status)
        self.requests = FakeRequests(self.trip, self.request)
        self.events = FakeEvents()

    def accept(self) -> AcceptRequest:
        return AcceptRequest(trips=FakeTrips(self.trip), requests=self.requests, events=self.events)

    def decline(self) -> DeclineRequest:
        return DeclineRequest(
            trips=FakeTrips(self.trip), requests=self.requests, events=self.events
        )

    def cancel(self) -> CancelRequest:
        return CancelRequest(trips=FakeTrips(self.trip), requests=self.requests, events=self.events)

    def command(self, user_id: UUID, now: datetime = NOW) -> RequestActionCommand:
        return RequestActionCommand(request_id=self.request.id, user_id=user_id, now=now)

    @property
    def stored_status(self) -> RequestStatus:
        return self.requests.items[self.request.id].status


# ---------------------------------------------------------------- accept


async def test_driver_accepts_a_pending_request() -> None:
    s = Setup()

    result = await s.accept().execute(s.command(s.trip.driver_id))

    assert result.status == RequestStatus.ACCEPTED
    assert result.decided_at == NOW
    assert s.trip.seats_available == 1
    assert s.events.calls == [("accepted", s.request.id, None)]


@pytest.mark.parametrize("who", ["rider", "stranger"])
async def test_only_the_trips_driver_can_accept(who: str) -> None:
    s = Setup()
    user_id = s.request.rider_id if who == "rider" else uuid4()

    with pytest.raises(NotTripDriverError):
        await s.accept().execute(s.command(user_id))

    assert s.stored_status == RequestStatus.PENDING
    assert s.trip.seats_available == 2
    assert s.events.calls == []


async def test_accepting_an_unknown_request_is_not_found() -> None:
    s = Setup()
    command = RequestActionCommand(request_id=uuid4(), user_id=s.trip.driver_id, now=NOW)

    with pytest.raises(RequestNotFoundError):
        await s.accept().execute(command)


@pytest.mark.parametrize("status", NOT_PENDING)
async def test_only_a_pending_request_can_be_accepted(status: RequestStatus) -> None:
    s = Setup(status=status)

    with pytest.raises(RequestNotPendingError):
        await s.accept().execute(s.command(s.trip.driver_id))

    assert s.trip.seats_available == 2
    assert s.events.calls == []


async def test_accepting_when_no_seat_is_left_returns_seat_taken() -> None:
    s = Setup(seats_available=0)

    with pytest.raises(SeatTakenError):
        await s.accept().execute(s.command(s.trip.driver_id))

    assert s.trip.seats_available == 0
    assert s.events.calls == []


async def test_accepting_twice_publishes_once() -> None:
    s = Setup()
    command = s.command(s.trip.driver_id)
    await s.accept().execute(command)

    with pytest.raises(RequestNotPendingError):
        await s.accept().execute(command)

    assert len(s.events.calls) == 1
    assert s.trip.seats_available == 1


async def test_accepting_after_departure_is_rejected() -> None:
    s = Setup()
    command = s.command(s.trip.driver_id, now=DEPARTURE + timedelta(minutes=1))

    with pytest.raises(RequestNotPendingError):
        await s.accept().execute(command)

    assert s.stored_status == RequestStatus.PENDING
    assert s.trip.seats_available == 2
    assert s.events.calls == []


async def test_accepting_on_a_cancelled_trip_is_not_reported_as_seat_taken() -> None:
    s = Setup(trip_status=TripStatus.CANCELLED)

    with pytest.raises(RequestNotPendingError):
        await s.accept().execute(s.command(s.trip.driver_id))

    assert s.stored_status == RequestStatus.PENDING
    assert s.trip.seats_available == 2
    assert s.events.calls == []


# ---------------------------------------------------------------- decline


async def test_declining_a_pending_request_keeps_the_seats() -> None:
    s = Setup()

    result = await s.decline().execute(s.command(s.trip.driver_id))

    assert result.status == RequestStatus.DECLINED
    assert s.trip.seats_available == 2
    assert s.events.calls == [("declined", s.request.id, False)]


async def test_declining_an_accepted_request_gives_the_seat_back() -> None:
    s = Setup(status=RequestStatus.ACCEPTED, seats_available=1)

    await s.decline().execute(s.command(s.trip.driver_id))

    assert s.trip.seats_available == 2
    assert s.events.calls == [("declined", s.request.id, True)]


async def test_only_the_trips_driver_can_decline() -> None:
    s = Setup()

    with pytest.raises(NotTripDriverError):
        await s.decline().execute(s.command(s.request.rider_id))

    assert s.stored_status == RequestStatus.PENDING
    assert s.events.calls == []


@pytest.mark.parametrize("status", FINISHED)
async def test_a_finished_request_cannot_be_declined(status: RequestStatus) -> None:
    s = Setup(status=status)

    with pytest.raises(RequestNotDecidableError):
        await s.decline().execute(s.command(s.trip.driver_id))

    assert s.trip.seats_available == 2
    assert s.events.calls == []


async def test_declining_after_departure_is_rejected() -> None:
    s = Setup(status=RequestStatus.ACCEPTED, seats_available=1)
    command = s.command(s.trip.driver_id, now=DEPARTURE + timedelta(minutes=1))

    with pytest.raises(RequestNotDecidableError):
        await s.decline().execute(command)

    assert s.trip.seats_available == 1
    assert s.events.calls == []


async def test_declining_on_a_cancelled_trip_is_rejected() -> None:
    s = Setup(trip_status=TripStatus.CANCELLED)

    with pytest.raises(RequestNotDecidableError):
        await s.decline().execute(s.command(s.trip.driver_id))


# ---------------------------------------------------------------- cancel


async def test_rider_cancels_a_pending_request() -> None:
    s = Setup()

    result = await s.cancel().execute(s.command(s.request.rider_id))

    assert result.status == RequestStatus.CANCELLED
    assert s.trip.seats_available == 2
    assert s.events.calls == [("cancelled", s.request.id, False)]


async def test_rider_cancelling_an_accepted_request_gives_the_seat_back() -> None:
    s = Setup(status=RequestStatus.ACCEPTED, seats_available=1)

    await s.cancel().execute(s.command(s.request.rider_id))

    assert s.trip.seats_available == 2
    assert s.events.calls == [("cancelled", s.request.id, True)]


@pytest.mark.parametrize("who", ["driver", "stranger"])
async def test_only_the_rider_can_cancel(who: str) -> None:
    s = Setup()
    user_id = s.trip.driver_id if who == "driver" else uuid4()

    with pytest.raises(NotYourRequestError):
        await s.cancel().execute(s.command(user_id))

    assert s.stored_status == RequestStatus.PENDING
    assert s.events.calls == []


@pytest.mark.parametrize("status", FINISHED)
async def test_a_finished_request_cannot_be_cancelled(status: RequestStatus) -> None:
    s = Setup(status=status)

    with pytest.raises(RequestNotCancellableError):
        await s.cancel().execute(s.command(s.request.rider_id))

    assert s.events.calls == []


async def test_cancelling_after_departure_is_rejected() -> None:
    s = Setup(status=RequestStatus.ACCEPTED, seats_available=1)
    command = s.command(s.request.rider_id, now=DEPARTURE + timedelta(minutes=1))

    with pytest.raises(RequestNotCancellableError):
        await s.cancel().execute(command)

    assert s.trip.seats_available == 1


async def test_cancelling_twice_gives_back_one_seat_and_publishes_once() -> None:
    s = Setup(status=RequestStatus.ACCEPTED, seats_available=1)
    command = s.command(s.request.rider_id)
    await s.cancel().execute(command)

    with pytest.raises(RequestNotCancellableError):
        await s.cancel().execute(command)

    assert s.trip.seats_available == 2
    assert len(s.events.calls) == 1
