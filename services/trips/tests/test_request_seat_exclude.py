"""exclude on the seat-request command reaches Routing's pickup selection."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from trips.application.request_routing import DetourEstimate, SelectedPickup
from trips.application.request_seat import RequestSeat, RequestSeatCommand
from trips.domain.entities import Trip
from trips.domain.request_errors import PickupNotAvailableError
from trips.domain.values import Direction, Location, Point, Quote

NOW = datetime(2030, 1, 1, 8, 0, tzinfo=UTC)


class ExcludeAwareRouting:
    """Offers s50 only when the request says to exclude s42."""

    async def select_pickup(self, *, trip_id, rider, pickup_id, exclude=()):
        if pickup_id != "s50" or tuple(exclude) != ("s42",):
            raise PickupNotAvailableError()
        return SelectedPickup(
            id="s50",
            location=Location("Pickup s50", 49.815, -97.14),
            walk_seconds=120,
            meters_to_trip_end=4000,
        )

    async def estimate_detour(self, *, trip_id, accepted_pickups, new_pickup):
        return DetourEstimate(added_seconds=180, position=1, total_seconds=1080)


def make_use_case() -> tuple[RequestSeat, Trip]:
    trip = Trip.create(
        driver_id=uuid4(),
        direction=Direction.TO_CAMPUS,
        place=Location("Pembina Highway", 49.82, -97.15),
        departure_at=NOW + timedelta(days=1),
        duration_seconds=900,
        distance_meters=6000,
        seats_total=3,
    )
    trips = AsyncMock()
    trips.get.return_value = trip
    requests = AsyncMock()
    requests.get_active_for_trip.return_value = None
    requests.has_overlapping_active_request.return_value = False
    requests.list_accepted_pickups.return_value = []
    pricing = AsyncMock()
    pricing.quote.return_value = Quote(200, "CAD", "4 km at $0.45/km ($2.00 minimum)")
    cards = AsyncMock()
    cards.has_card.return_value = True
    use_case = RequestSeat(
        trips=trips,
        requests=requests,
        routing=ExcludeAwareRouting(),
        pricing=pricing,
        cards=cards,
        events=AsyncMock(),
    )
    return use_case, trip


def command_for(trip: Trip, exclude: tuple[str, ...]) -> RequestSeatCommand:
    return RequestSeatCommand(
        trip_id=trip.id,
        rider_id=uuid4(),
        rider=Point(lat=49.8722, lng=-97.1561),
        pickup_id="s50",
        now=NOW,
        exclude=exclude,
    )


async def test_exclude_reaches_routing_and_the_request_is_created() -> None:
    use_case, trip = make_use_case()

    request = await use_case.execute(command_for(trip, exclude=("s42",)))

    assert request.pickup.label == "Pickup s50"


async def test_without_exclude_the_pickup_is_not_available() -> None:
    use_case, trip = make_use_case()

    with pytest.raises(PickupNotAvailableError):
        await use_case.execute(command_for(trip, exclude=()))
