"""Application use case for one trip's detail, with the rider's pickup points (#30).

1. The trip.
2. If the rider sent their location: up to 3 pickup points from Routing (#29), each with its
   walking time, never one they rejected (``exclude``, #136). Only for a scheduled trip, and
   not for its own driver, who can't ride it.
3. The rider's share for each point, priced like search (``ride_meters``), so the first point
   and its cost match what search showed for the same trip and spot. A price is a nice to
   have: if Payments can't answer, the point is still shown, without a cost.
4. The viewer's own pending or accepted request on the trip (#350), so a reload still shows
   it. With one, no new pickup points are worked out: the request's pickup is the one that
   counts, and Routing being down can't hide the request.

The rider's location is passed to Routing and never stored. Hiding the driver's own end from
everyone else is the API's job: it's a view of the trip, not a rule about finding it.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from trips.application.ports import (
    PricingService,
    RiderRequestLookup,
    RoutingService,
    TripRepository,
)
from trips.domain.entities import Trip
from trips.domain.errors import PricingUnavailableError, TripNotFoundError
from trips.domain.seat_request import SeatRequest
from trips.domain.values import PickupOffer, Point, Quote, TripStatus, ride_meters

# The contract's limit for the trip detail.
PICKUPS_PER_TRIP = 3


@dataclass(frozen=True)
class PricedPickup:
    offer: PickupOffer
    cost: Quote | None


@dataclass(frozen=True)
class TripDetailResult:
    trip: Trip
    viewer_is_driver: bool
    pickups: list[PricedPickup]
    my_request: SeatRequest | None = None  # the viewer's pending or accepted request (#350)


class GetTripDetail:
    def __init__(
        self,
        repository: TripRepository,
        routing: RoutingService,
        pricing: PricingService,
        requests: RiderRequestLookup,
    ) -> None:
        self.repository = repository
        self.routing = routing
        self.pricing = pricing
        self.requests = requests

    async def execute(
        self,
        trip_id: UUID,
        viewer_id: UUID,
        rider: Point | None = None,
        exclude: Sequence[str] = (),
    ) -> TripDetailResult:
        trip = await self.repository.get(trip_id)
        if trip is None:
            raise TripNotFoundError()

        viewer_is_driver = viewer_id == trip.driver_id
        # The driver can't ride their own trip, so they never have a request on it.
        my_request = (
            None
            if viewer_is_driver
            else await self.requests.get_active_for_trip(trip.id, viewer_id)
        )
        if (
            rider is None
            or viewer_is_driver
            or my_request is not None
            or trip.status != TripStatus.SCHEDULED
        ):
            return TripDetailResult(trip, viewer_is_driver, pickups=[], my_request=my_request)

        offers = await self.routing.pickup_points(trip.id, rider, PICKUPS_PER_TRIP, exclude)
        costs = await asyncio.gather(
            *(
                self._cost(ride_meters(trip.direction, trip.distance_meters, o.meters_to_trip_end))
                for o in offers
            )
        )
        pickups = [PricedPickup(o, c) for o, c in zip(offers, costs, strict=True)]
        return TripDetailResult(trip, viewer_is_driver, pickups)

    async def _cost(self, distance_meters: int) -> Quote | None:
        try:
            return await self.pricing.quote(distance_meters)
        except PricingUnavailableError:
            return None
