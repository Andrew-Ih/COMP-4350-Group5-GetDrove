"""Application use case for one trip's detail, with the rider's pickup points (#30).

1. The trip.
2. If the rider sent their location: up to 3 pickup points from Routing (#29), each with its
   walking time, never one they rejected (``exclude``, #136). Only for a scheduled trip, and
   not for its own driver, who can't ride it.
3. The rider's share for each point, priced like search (``ride_meters``), so the first point
   and its cost match what search showed for the same trip and spot. A price is a nice to
   have: if Payments can't answer, the point is still shown, without a cost.

The rider's location is passed to Routing and never stored. Hiding the driver's own end from
everyone else is the API's job: it's a view of the trip, not a rule about finding it.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from trips.application.ports import PricingService, RoutingService, TripRepository
from trips.domain.entities import Trip
from trips.domain.errors import PricingUnavailableError, TripNotFoundError
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


class GetTripDetail:
    def __init__(
        self, repository: TripRepository, routing: RoutingService, pricing: PricingService
    ) -> None:
        self.repository = repository
        self.routing = routing
        self.pricing = pricing

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
        if rider is None or viewer_is_driver or trip.status != TripStatus.SCHEDULED:
            return TripDetailResult(trip, viewer_is_driver, pickups=[])

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
