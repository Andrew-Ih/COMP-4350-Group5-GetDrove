"""Request-seat orchestration tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from trips.application.request_routing import DetourEstimate, SelectedPickup
from trips.application.request_seat import RequestSeat, RequestSeatCommand
from trips.domain.entities import Trip
from trips.domain.errors import PricingUnavailableError, RoutingUnavailableError
from trips.domain.request_errors import (
    AlreadyRequestedError,
    CardRequiredError,
    CardStatusUnavailableError,
    OverlappingRequestError,
    OwnTripError,
    TripFullError,
    TripNotFoundError,
    TripNotOpenError,
)
from trips.domain.seat_request import SeatRequest
from trips.domain.values import Direction, Location, Point, Quote, TripStatus

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2029, 12, 31, tzinfo=UTC)
PICKUP = SelectedPickup(
    id="s42",
    location=Location("Pembina pickup", 49.82, -97.15),
    walk_seconds=120,
    meters_to_trip_end=4000,
)


def make_trip(
    *,
    seats_available: int = 2,
    status: TripStatus = TripStatus.SCHEDULED,
    driver_id: UUID | None = None,
    departure_at: datetime = DEPARTURE,
) -> Trip:
    return Trip(
        id=uuid4(),
        driver_id=driver_id or uuid4(),
        direction=Direction.TO_CAMPUS,
        origin=Location("Home", 49.8, -97.2),
        destination=Location("Campus", 49.8075, -97.1366),
        departure_at=departure_at,
        estimated_arrival_at=departure_at.replace(hour=10),
        duration_seconds=3600,
        distance_meters=10000,
        seats_total=3,
        seats_available=seats_available,
        status=status,
    )


def make_command(trip_id: UUID | None = None, rider_id: UUID | None = None) -> RequestSeatCommand:
    return RequestSeatCommand(
        trip_id=trip_id or uuid4(),
        rider_id=rider_id or uuid4(),
        rider=Point(49.821, -97.151),
        pickup_id="s42",
        now=NOW,
    )


def make_existing(trip_id: UUID) -> SeatRequest:
    return SeatRequest.create(
        trip_id=trip_id,
        rider_id=uuid4(),
        pickup=PICKUP.location,
        walk_seconds=1,
        rider_distance_meters=1,
        detour_seconds=None,
        cost=Quote(200, "CAD", "existing"),
        now=NOW,
    )


class FakeTrips:
    def __init__(self, trip: Trip | None) -> None:
        self.trip = trip

    async def get(self, trip_id: UUID) -> Trip | None:
        return self.trip


class FakeRequests:
    def __init__(self, *, existing: SeatRequest | None, overlapping: bool) -> None:
        self.existing = existing
        self.overlapping = overlapping
        self.saved: list[SeatRequest] = []

    async def get_active_for_trip(self, trip_id: UUID, rider_id: UUID) -> SeatRequest | None:
        return self.existing

    async def has_overlapping_active_request(
        self, rider_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> bool:
        return self.overlapping

    async def list_accepted_pickups(self, trip_id: UUID) -> list[Location]:
        return []

    async def add(self, request: SeatRequest) -> None:
        self.saved.append(request)


class FakeRouting:
    def __init__(self, *, pickup_error: Exception | None, detour_error: Exception | None) -> None:
        self.pickup_error = pickup_error
        self.detour_error = detour_error

    async def select_pickup(self, **kwargs: object) -> SelectedPickup:
        if self.pickup_error is not None:
            raise self.pickup_error
        return PICKUP

    async def estimate_detour(self, **kwargs: object) -> DetourEstimate:
        if self.detour_error is not None:
            raise self.detour_error
        return DetourEstimate(180, 1, 1500)


class FakePricing:
    def __init__(self, error: Exception | None) -> None:
        self.error = error

    async def quote(self, distance_meters: int) -> Quote:
        if self.error is not None:
            raise self.error
        return Quote(450, "CAD", "$4.50 for 10 km")


class FakeCards:
    def __init__(self, *, has_card: bool, error: Exception | None) -> None:
        self.has_card_result = has_card
        self.error = error
        self.calls = 0

    async def has_card(self, rider_id: UUID) -> bool:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.has_card_result


class FakeEvents:
    def __init__(self) -> None:
        self.published: list[SeatRequest] = []
        self.trips: list[Trip] = []

    async def seat_requested(self, request: SeatRequest, trip: Trip) -> None:
        self.published.append(request)
        self.trips.append(trip)


@dataclass
class Harness:
    use_case: RequestSeat
    requests: FakeRequests
    cards: FakeCards
    events: FakeEvents


def build(
    trip: Trip | None,
    *,
    existing: SeatRequest | None = None,
    overlapping: bool = False,
    has_card: bool = True,
    card_error: Exception | None = None,
    pickup_error: Exception | None = None,
    detour_error: Exception | None = None,
    pricing_error: Exception | None = None,
) -> Harness:
    requests = FakeRequests(existing=existing, overlapping=overlapping)
    cards = FakeCards(has_card=has_card, error=card_error)
    events = FakeEvents()
    use_case = RequestSeat(
        trips=FakeTrips(trip),
        requests=requests,
        routing=FakeRouting(pickup_error=pickup_error, detour_error=detour_error),
        pricing=FakePricing(pricing_error),
        cards=cards,
        events=events,
    )
    return Harness(use_case, requests, cards, events)


async def test_creates_pending_request_with_price_detour_and_event() -> None:
    trip = make_trip()
    harness = build(trip)
    command = make_command(trip.id)

    request = await harness.use_case.execute(command)

    assert request.trip_id == trip.id
    assert request.rider_id == command.rider_id
    assert request.pickup == PICKUP.location
    assert request.walk_seconds == 120
    assert request.rider_distance_meters == 4000
    assert request.detour_seconds == 180
    assert request.cost == Quote(450, "CAD", "$4.50 for 10 km")
    assert request.status.value == "pending"
    assert request.auto_accepted is False
    assert harness.requests.saved == [request]
    assert harness.events.published == [request]
    assert harness.events.trips == [trip]


async def test_unknown_trip_is_rejected_without_calling_payments() -> None:
    harness = build(None)

    with pytest.raises(TripNotFoundError):
        await harness.use_case.execute(make_command())

    assert harness.cards.calls == 0


async def test_own_trip_is_rejected() -> None:
    rider_id = uuid4()
    trip = make_trip(driver_id=rider_id)
    harness = build(trip)

    with pytest.raises(OwnTripError):
        await harness.use_case.execute(make_command(trip.id, rider_id))


async def test_full_trip_is_rejected_without_calling_payments() -> None:
    trip = make_trip(seats_available=0)
    harness = build(trip)

    with pytest.raises(TripFullError):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.cards.calls == 0
    assert harness.requests.saved == []


async def test_cancelled_trip_is_rejected() -> None:
    trip = make_trip(status=TripStatus.CANCELLED)

    with pytest.raises(TripNotOpenError):
        await build(trip).use_case.execute(make_command(trip.id))


async def test_trip_that_already_left_is_rejected() -> None:
    trip = make_trip(departure_at=datetime(2020, 1, 1, 9, 0, tzinfo=UTC))

    with pytest.raises(TripNotOpenError):
        await build(trip).use_case.execute(make_command(trip.id))


async def test_duplicate_request_is_rejected() -> None:
    trip = make_trip()
    harness = build(trip, existing=make_existing(trip.id))

    with pytest.raises(AlreadyRequestedError):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.requests.saved == []


async def test_overlapping_request_is_rejected() -> None:
    trip = make_trip()
    harness = build(trip, overlapping=True)

    with pytest.raises(OverlappingRequestError):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.requests.saved == []


async def test_missing_card_is_rejected() -> None:
    trip = make_trip()
    harness = build(trip, has_card=False)

    with pytest.raises(CardRequiredError):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.requests.saved == []


async def test_card_lookup_failure_is_not_treated_as_no_card() -> None:
    trip = make_trip()
    harness = build(trip, card_error=CardStatusUnavailableError())

    with pytest.raises(CardStatusUnavailableError):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.requests.saved == []


@pytest.mark.parametrize("failure", ["pickup", "detour", "pricing"])
async def test_external_failures_do_not_save_a_request(failure: str) -> None:
    trip = make_trip()
    harness = build(
        trip,
        pickup_error=RoutingUnavailableError() if failure == "pickup" else None,
        detour_error=RoutingUnavailableError() if failure == "detour" else None,
        pricing_error=PricingUnavailableError() if failure == "pricing" else None,
    )

    with pytest.raises((RoutingUnavailableError, PricingUnavailableError)):
        await harness.use_case.execute(make_command(trip.id))

    assert harness.requests.saved == []
    assert harness.events.published == []
