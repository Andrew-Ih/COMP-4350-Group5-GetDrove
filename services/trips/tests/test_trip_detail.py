"""Unit tests for the trip detail (#30): the GetTripDetail use case with fakes, and the call
to Routing's pickup points."""

import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from trips.adapters.routing import HTTPRoutingService
from trips.application.trip_detail import PICKUPS_PER_TRIP, GetTripDetail
from trips.domain.entities import Trip
from trips.domain.errors import (
    PricingUnavailableError,
    RoutingUnavailableError,
    TripNotFoundError,
)
from trips.domain.values import Direction, Location, PickupOffer, Point, Quote, TripStatus

type Handler = Callable[[httpx.Request], httpx.Response]

RIDER = Point(lat=49.85, lng=-97.15)
DRIVER = uuid4()
RIDER_ID = uuid4()


def trip(direction: Direction = Direction.TO_CAMPUS) -> Trip:
    """A 6 km trip."""
    return Trip.create(
        driver_id=DRIVER,
        direction=direction,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=datetime.now(UTC) + timedelta(days=1),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )


def offer(id_: str, walk: int, to_end: int) -> PickupOffer:
    return PickupOffer(
        id=id_,
        pickup=Location("Pembina Highway", 49.84, -97.15),
        walk_seconds=walk,
        meters_to_trip_end=to_end,
    )


class FakeRepository:
    def __init__(self, *trips: Trip) -> None:
        self.trips = {t.id: t for t in trips}

    async def get(self, trip_id: UUID) -> Trip | None:
        return self.trips.get(trip_id)


class FakeRouting:
    def __init__(self, offers: list[PickupOffer], error: Exception | None = None) -> None:
        self.offers, self.error = offers, error
        self.calls: list[tuple[UUID, Point, int, list[str]]] = []

    async def pickup_points(
        self, trip_id: UUID, rider: Point, limit: int, exclude: Sequence[str]
    ) -> list[PickupOffer]:
        self.calls.append((trip_id, rider, limit, list(exclude)))
        if self.error:
            raise self.error
        return self.offers


class FakePricing:
    def __init__(self, fail_for: set[int] | None = None) -> None:
        self.fail_for = fail_for or set()
        self.asked: list[int] = []

    async def quote(self, distance_meters: int) -> Quote:
        self.asked.append(distance_meters)
        if distance_meters in self.fail_for:
            raise PricingUnavailableError()
        return Quote(distance_meters * 45 // 1000, "CAD", f"{distance_meters / 1000:.1f} km")


def detail(
    the_trip: Trip, routing: FakeRouting, pricing: FakePricing | None = None
) -> GetTripDetail:
    return GetTripDetail(FakeRepository(the_trip), routing, pricing or FakePricing())


# ---------------------------------------------------------------- the use case


async def test_a_rider_gets_the_trip_with_priced_pickup_points() -> None:
    the_trip = trip()
    routing = FakeRouting([offer("s12", 120, 4000), offer("s15", 300, 3700)])
    pricing = FakePricing()

    result = await detail(the_trip, routing, pricing).execute(the_trip.id, RIDER_ID, RIDER)

    assert result.trip == the_trip
    assert result.viewer_is_driver is False
    assert [(p.offer.id, p.cost) for p in result.pickups] == [
        ("s12", Quote(180, "CAD", "4.0 km")),
        ("s15", Quote(166, "CAD", "3.7 km")),
    ]
    # Up to 3 points, for this trip and rider.
    assert routing.calls == [(the_trip.id, RIDER, PICKUPS_PER_TRIP, [])]


async def test_leaving_campus_each_point_is_priced_from_campus_to_it() -> None:
    """The same rule as search (ride_meters), so a point costs the same in both."""
    the_trip = trip(Direction.FROM_CAMPUS)
    pricing = FakePricing()

    await detail(the_trip, FakeRouting([offer("s40", 120, 1000)]), pricing).execute(
        the_trip.id, RIDER_ID, RIDER
    )

    assert pricing.asked == [5000]  # 6 km trip, dropped off 1 km before its end


async def test_rejected_points_are_passed_on_to_routing() -> None:
    the_trip = trip()
    routing = FakeRouting([offer("s20", 120, 4000)])

    await detail(the_trip, routing).execute(the_trip.id, RIDER_ID, RIDER, exclude=["s12", "s15"])

    assert routing.calls[0][3] == ["s12", "s15"]


async def test_a_point_without_a_price_is_still_shown() -> None:
    the_trip = trip()
    routing = FakeRouting([offer("s12", 120, 4000), offer("s15", 300, 3700)])

    result = await detail(the_trip, routing, FakePricing(fail_for={3700})).execute(
        the_trip.id, RIDER_ID, RIDER
    )

    assert [(p.offer.id, p.cost is None) for p in result.pickups] == [
        ("s12", False),
        ("s15", True),
    ]


async def test_without_the_riders_location_there_are_no_pickups_and_no_routing_call() -> None:
    the_trip = trip()
    routing = FakeRouting([offer("s12", 120, 4000)])

    result = await detail(the_trip, routing).execute(the_trip.id, RIDER_ID)

    assert result.pickups == []
    assert routing.calls == []


async def test_the_driver_gets_their_trip_without_pickups() -> None:
    """They can't ride their own trip."""
    the_trip = trip()
    routing = FakeRouting([offer("s12", 120, 4000)])

    result = await detail(the_trip, routing).execute(the_trip.id, DRIVER, RIDER)

    assert result.viewer_is_driver is True
    assert result.pickups == []
    assert routing.calls == []


@pytest.mark.parametrize(
    "status", [TripStatus.CANCELLED, TripStatus.IN_PROGRESS, TripStatus.COMPLETED]
)
async def test_a_trip_that_cant_be_ridden_any_more_has_no_pickups(status: TripStatus) -> None:
    the_trip = replace(trip(), status=status)
    routing = FakeRouting([offer("s12", 120, 4000)])

    result = await detail(the_trip, routing).execute(the_trip.id, RIDER_ID, RIDER)

    assert result.trip.status == status
    assert result.pickups == []
    assert routing.calls == []


async def test_an_unknown_trip_is_not_found() -> None:
    with pytest.raises(TripNotFoundError):
        await detail(trip(), FakeRouting([])).execute(uuid4(), RIDER_ID, RIDER)


async def test_routing_down_is_an_error() -> None:
    the_trip = trip()
    routing = FakeRouting([], error=RoutingUnavailableError())

    with pytest.raises(RoutingUnavailableError):
        await detail(the_trip, routing).execute(the_trip.id, RIDER_ID, RIDER)


# ---------------------------------------------------------------- Routing: pickup points


def points(*ids: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pickups": [
                    {
                        "id": id_,
                        "label": "Pembina Highway",
                        "lat": 49.84,
                        "lng": -97.15,
                        "walkSeconds": 120,
                        "riderDistanceMeters": 4000,
                    }
                    for id_ in ids
                ]
            },
        )

    return handler


async def pickup_points(
    handler: Handler, limit: int = 3, exclude: Sequence[str] = ()
) -> list[PickupOffer]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        return await HTTPRoutingService(client).pickup_points(uuid4(), RIDER, limit, exclude)


async def test_pickup_points_sends_the_trip_rider_limit_and_rejected_points() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return points("s20")(request)

    result = await pickup_points(handler, exclude=["s12"])

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/internal/pickup-points"
    body = json.loads(request.content)
    assert (body["rider"], body["limit"], body["exclude"]) == (
        {"lat": 49.85, "lng": -97.15},
        3,
        ["s12"],
    )
    assert result == [offer("s20", 120, 4000)]


async def test_a_trip_without_a_route_has_no_pickup_points() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": "route_not_found"})

    assert await pickup_points(handler) == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, json={"code": "routing_engine_unavailable"}),
        httpx.Response(422, json={"code": "invalid_input"}),
        httpx.Response(200, content=b"not JSON"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"pickups": [{"id": 42}]}),
    ],
)
async def test_pickup_points_failure_is_routing_unavailable(response: httpx.Response) -> None:
    with pytest.raises(RoutingUnavailableError) as error:
        await pickup_points(lambda request: response)

    assert "Pickup points can't be worked out" in str(error.value)


@pytest.mark.parametrize(
    ("handler", "limit", "exclude"),
    [
        (points("s1", "s2", "s3", "s4"), 3, ()),  # more than asked for
        (points("s12"), 3, ("s12",)),  # one the rider rejected
    ],
)
async def test_routing_may_only_answer_what_it_was_asked(
    handler: Handler, limit: int, exclude: tuple[str, ...]
) -> None:
    with pytest.raises(RoutingUnavailableError):
        await pickup_points(handler, limit, exclude)


async def test_pickup_points_timeout_is_routing_unavailable() -> None:
    def handler(request: httpx.Request) -> Any:
        raise httpx.ReadTimeout("Routing timed out", request=request)

    with pytest.raises(RoutingUnavailableError):
        await pickup_points(handler)
