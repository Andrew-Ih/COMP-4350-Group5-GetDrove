"""Auto-accepting a new seat request (#43), with in-memory fakes: when it happens, and that
anything unknown leaves the request pending for the driver."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from trips.application.ports import RiderProfile
from trips.application.request_routing import DetourEstimate, SelectedPickup
from trips.application.request_seat import RequestSeat, RequestSeatCommand
from trips.domain.auto_accept import AutoAcceptRules
from trips.domain.entities import Trip
from trips.domain.errors import RoutingUnavailableError
from trips.domain.request_errors import AccountsUnavailableError
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import Direction, Location, Point, Quote, TripStatus

DEPARTURE = datetime(2030, 1, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2029, 12, 31, tzinfo=UTC)
PICKUP = SelectedPickup("s42", Location("Pembina pickup", 49.82, -97.15), 120, 4000)
DETOUR_SECONDS = 180  # what FakeRouting says the pickup adds: 3 minutes
ON = AutoAcceptRules(enabled=True, max_detour_minutes=5, min_rating=None)


def make_trip(seats_available: int = 2) -> Trip:
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
        status=TripStatus.SCHEDULED,
    )


class FakeTrips:
    def __init__(self, trip: Trip) -> None:
        self.trip = trip

    async def get(self, trip_id: UUID) -> Trip | None:
        return self.trip


class FakeRequests:
    """``pickups``: the accepted pickups on each call, in order (first when the detour is
    estimated, then under the trip lock). The last one repeats."""

    def __init__(self, *, seat_free: bool, pickups: list[list[Location]] | None = None) -> None:
        self.seat_free = seat_free
        self.pickups = pickups or [[]]
        self.added: list[SeatRequest] = []
        self.decisions: list[SeatRequest] = []
        self.seats_taken = 0
        self.placed_at: list[int | None] = []

    async def lock_rider(self, rider_id: UUID) -> None: ...

    async def lock_trip(self, trip_id: UUID) -> None: ...

    async def get_active_for_trip(self, trip_id: UUID, rider_id: UUID) -> SeatRequest | None:
        return None

    async def has_overlapping_active_request(self, *args: object) -> bool:
        return False

    async def list_accepted_pickups(self, trip_id: UUID) -> list[Location]:
        return self.pickups.pop(0) if len(self.pickups) > 1 else self.pickups[0]

    async def add(self, request: SeatRequest) -> None:
        self.added.append(request)

    async def take_seat(self, trip_id: UUID) -> bool:
        if not self.seat_free:
            return False
        self.seats_taken += 1
        return True

    async def save_decision(self, request: SeatRequest, *, expected: RequestStatus) -> bool:
        assert expected is RequestStatus.PENDING
        self.decisions.append(request)
        return True

    async def place_accepted(self, request: SeatRequest, *, position: int | None) -> int:
        self.placed_at.append(position)
        return 1


class FakeRouting:
    """``detours``: what each estimate returns, in order (an exception is raised). The last
    one repeats."""

    def __init__(self, detours: list[DetourEstimate | Exception] | None = None) -> None:
        self.detours = detours or [DetourEstimate(DETOUR_SECONDS, 0, 1080)]
        self.estimates = 0

    async def select_pickup(self, **kwargs: object) -> SelectedPickup:
        return PICKUP

    async def estimate_detour(self, **kwargs: object) -> DetourEstimate:
        answer = self.detours[min(self.estimates, len(self.detours) - 1)]
        self.estimates += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakePricing:
    async def quote(self, distance_meters: int) -> Quote:
        return Quote(450, "CAD", "$4.50")


class FakeCards:
    async def has_card(self, rider_id: UUID) -> bool:
        return True


class FakeEvents:
    def __init__(self) -> None:
        self.requested: list[SeatRequest] = []
        self.accepted: list[SeatRequest] = []

    async def seat_requested(self, request: SeatRequest, trip: Trip) -> None:
        self.requested.append(request)

    async def request_accepted(self, request: SeatRequest, trip: Trip) -> None:
        self.accepted.append(request)


class FakeRules:
    def __init__(self, rules: AutoAcceptRules | None) -> None:
        self.rules = rules

    async def get(self, driver_id: UUID) -> AutoAcceptRules | None:
        return self.rules


class FakeRiders:
    """Accounts: ``ratings`` maps riders to their rating; unlisted riders are unknown."""

    def __init__(self, ratings: dict[UUID, float | None], *, down: bool = False) -> None:
        self.ratings = ratings
        self.down = down
        self.calls = 0

    async def get_many(self, rider_ids: object) -> dict[UUID, RiderProfile]:
        self.calls += 1
        if self.down:
            raise AccountsUnavailableError()
        return {
            rider: RiderProfile(rider, "Priya", rating, 3 if rating else 0, 0)
            for rider, rating in self.ratings.items()
        }


@dataclass
class Run:
    result: SeatRequest
    requests: FakeRequests
    events: FakeEvents
    riders: FakeRiders
    routing: FakeRouting


async def request_seat(
    rules: AutoAcceptRules | None,
    *,
    rating: float | None = None,
    rider_known: bool = True,
    accounts_down: bool = False,
    seat_free: bool = True,
    seats_available: int = 2,
    pickups: list[list[Location]] | None = None,
    detours: list[DetourEstimate | Exception] | None = None,
) -> Run:
    rider = uuid4()
    trip = make_trip(seats_available)
    requests, events = FakeRequests(seat_free=seat_free, pickups=pickups), FakeEvents()
    routing = FakeRouting(detours)
    riders = FakeRiders({rider: rating} if rider_known else {}, down=accounts_down)
    use_case = RequestSeat(
        trips=FakeTrips(trip),
        requests=requests,  # type: ignore[arg-type]
        routing=routing,
        pricing=FakePricing(),
        cards=FakeCards(),
        events=events,  # type: ignore[arg-type]
        auto_accept=FakeRules(rules),
        riders=riders,
    )
    command = RequestSeatCommand(trip.id, rider, Point(49.821, -97.151), "s42", NOW)
    return Run(await use_case.execute(command), requests, events, riders, routing)


async def test_a_request_meeting_the_rules_is_accepted_and_the_rider_notified() -> None:
    run = await request_seat(ON)

    assert run.result.status is RequestStatus.ACCEPTED
    assert run.result.auto_accepted
    assert run.result.decided_at == NOW
    assert run.result.pickup_order == 1
    assert run.requests.seats_taken == 1
    assert [d.auto_accepted for d in run.requests.decisions] == [True]
    # Saved pending first, then accepted. Only RequestAccepted is published, not
    # SeatRequested (seat-requested.v1), so the driver isn't asked to accept a rider who's
    # already in.
    assert run.requests.added[0].status is RequestStatus.PENDING
    assert [r.id for r in run.events.accepted] == [run.result.id]
    assert run.events.requested == []


async def test_without_rules_the_request_waits_for_the_driver() -> None:
    run = await request_seat(None)

    assert run.result.status is RequestStatus.PENDING
    assert not run.result.auto_accepted
    assert run.requests.seats_taken == 0
    assert run.events.accepted == []
    assert [r.id for r in run.events.requested] == [run.result.id]  # the driver is asked


async def test_a_detour_over_the_limit_waits_for_the_driver() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, max_detour_minutes=2))  # 120s < 180s

    assert run.result.status is RequestStatus.PENDING


async def test_a_rider_rated_high_enough_is_accepted() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, min_rating=4.0), rating=4.5)

    assert run.result.status is RequestStatus.ACCEPTED
    assert run.riders.calls == 1


async def test_a_rider_rated_too_low_waits_for_the_driver() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, min_rating=4.0), rating=3.5)

    assert run.result.status is RequestStatus.PENDING


async def test_a_rider_with_no_ratings_yet_passes() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, min_rating=4.0), rating=None)

    assert run.result.status is RequestStatus.ACCEPTED


async def test_if_accounts_cant_answer_the_request_waits_and_nothing_fails() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, min_rating=4.0), accounts_down=True)

    assert run.result.status is RequestStatus.PENDING
    assert len(run.requests.added) == 1  # the request itself is still made


async def test_a_rider_accounts_doesnt_know_waits_for_the_driver() -> None:
    run = await request_seat(AutoAcceptRules(enabled=True, min_rating=4.0), rider_known=False)

    assert run.result.status is RequestStatus.PENDING


async def test_without_a_minimum_rating_accounts_isnt_asked() -> None:
    run = await request_seat(ON, accounts_down=True)

    assert run.result.status is RequestStatus.ACCEPTED
    assert run.riders.calls == 0


async def test_if_the_last_seat_goes_first_the_request_stays_pending() -> None:
    """The trip showed a seat, but another accept took it: take_seat refuses, and nothing
    else changes."""
    run = await request_seat(ON, seat_free=False)

    assert run.result.status is RequestStatus.PENDING
    assert run.requests.decisions == []
    assert run.events.accepted == []
    assert len(run.events.requested) == 1  # a normal request for the driver now


# ---------------------------------------------------------------- pickups changing (review)

OTHER_PICKUP = Location("Osborne pickup", 49.87, -97.14)


async def test_unchanged_pickups_arent_estimated_twice() -> None:
    run = await request_seat(ON)

    assert run.routing.estimates == 1


async def test_if_another_pickup_was_accepted_meanwhile_the_new_detour_decides() -> None:
    """Estimated with no accepted pickups (3 minutes), but by the time the trip is locked
    another rider was accepted, and the detour is now 6 minutes: over the 5-minute limit."""
    run = await request_seat(
        ON,
        pickups=[[], [OTHER_PICKUP]],
        detours=[DetourEstimate(180, 0, 1080), DetourEstimate(360, 1, 1400)],
    )

    assert run.result.status is RequestStatus.PENDING
    assert run.routing.estimates == 2
    assert run.requests.added[0].detour_seconds == 360  # saved with the current detour
    assert len(run.events.requested) == 1


async def test_a_re_estimate_within_the_limit_accepts_at_the_new_position() -> None:
    run = await request_seat(
        ON,
        pickups=[[], [OTHER_PICKUP]],
        detours=[DetourEstimate(180, 0, 1080), DetourEstimate(240, 1, 1300)],
    )

    assert run.result.status is RequestStatus.ACCEPTED
    assert run.requests.placed_at == [1]  # the position from the second estimate, not 0
    assert run.result.detour_seconds == 240


async def test_if_routing_cant_re_estimate_the_request_waits_for_the_driver() -> None:
    run = await request_seat(
        ON,
        pickups=[[], [OTHER_PICKUP]],
        detours=[DetourEstimate(180, 0, 1080), RoutingUnavailableError("down")],
    )

    assert run.result.status is RequestStatus.PENDING
    assert len(run.requests.added) == 1  # the request is still made
    assert len(run.events.requested) == 1
