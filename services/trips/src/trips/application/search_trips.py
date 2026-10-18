"""Application use case for finding trips that pass near a rider (#97).

1. Trips: scheduled trips with a free seat in the rider's direction and time window.
2. Routing: which of them the rider can walk to, and where they'd be picked up (#26).
3. Payments: the rider's cost for each, from how far they'd ride (which depends on the
   direction: see ride_meters). A price is a nice to have: if Payments can't answer, the
   trip is still shown, without a cost.

Soonest departure first. The rider's location is passed to Routing and never stored.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from trips.application.ports import PricingService, RoutingService, TripRepository
from trips.domain.entities import Trip
from trips.domain.errors import PricingUnavailableError
from trips.domain.values import (
    Direction,
    Point,
    Quote,
    SearchWindow,
    TripMatch,
    ride_meters,
)


@dataclass(frozen=True)
class SearchResult:
    trip: Trip
    match: TripMatch
    cost: Quote | None


class SearchTrips:
    def __init__(
        self,
        repository: TripRepository,
        routing: RoutingService,
        pricing: PricingService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.routing = routing
        self.pricing = pricing
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, rider_id: UUID, rider: Point, direction: Direction, time: datetime
    ) -> list[SearchResult]:
        candidates = await self.repository.search(
            SearchWindow.for_rider(direction, time),
            departs_after=self.clock(),
            exclude_driver_id=rider_id,
        )
        if not candidates:
            return []

        trips = {trip.id: trip for trip in candidates}
        matches = [m for m in await self.routing.match(rider, list(trips)) if m.trip_id in trips]
        costs = await asyncio.gather(
            *(
                self._cost(ride_meters(direction, trips[m.trip_id].distance_meters, m))
                for m in matches
            )
        )

        results = [
            SearchResult(trip=trips[match.trip_id], match=match, cost=cost)
            for match, cost in zip(matches, costs, strict=True)
        ]
        return sorted(results, key=lambda r: (r.trip.departure_at, str(r.trip.id)))

    async def _cost(self, distance_meters: int) -> Quote | None:
        try:
            return await self.pricing.quote(distance_meters)
        except PricingUnavailableError:
            return None
