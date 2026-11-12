"""Application use case for finding the trips a rider can walk to (#26).

A trip matches if some point on its route is a pickup point for this rider; its best one is
returned. How points are chosen (corridor, private ends, walking time, excluded roads) is in
``routing.application.pickups``, shared with the pickup points endpoint (#29).

The rider's location is used for the calculation only, never stored or logged.
"""

import asyncio
from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from routing.application.pickups import Reachable, choose, offerable, walkable
from routing.application.ports import RouteRepository, RoutingEngine, WalkingEngine
from routing.domain.values import Corridor, LatLng, RiderMatch


class MatchRider:
    def __init__(
        self,
        repository: RouteRepository,
        walking: WalkingEngine,
        driving: RoutingEngine,
        corridor: Corridor,
        max_walk_seconds: int,
    ) -> None:
        self.repository = repository
        self.walking = walking
        self.driving = driving
        self.corridor = corridor
        self.max_walk_seconds = max_walk_seconds

    async def execute(self, rider: LatLng, trip_ids: Sequence[UUID]) -> list[RiderMatch]:
        if not trip_ids:
            return []

        hits = offerable(await self.repository.samples_in_corridor(rider, trip_ids, self.corridor))
        # One walking request for every trip's samples, then split by trip (still shortest
        # walk first within each).
        per_trip: dict[UUID, Reachable] = defaultdict(list)
        for hit, walk in await walkable(rider, hits, self.walking, self.max_walk_seconds):
            per_trip[hit.trip_id].append((hit, walk))

        # In the order Trips asked, without repeats.
        candidates = [trip_id for trip_id in dict.fromkeys(trip_ids) if trip_id in per_trip]
        best = await asyncio.gather(
            *(choose(per_trip[trip_id], self.driving, limit=1) for trip_id in candidates)
        )

        return [
            RiderMatch(
                trip_id=trip_id,
                pickup=pickup.point,
                pickup_label=pickup.label,
                walk_seconds=pickup.walk_seconds,
                rider_distance_meters=pickup.rider_distance_meters,
            )
            for trip_id, chosen in zip(candidates, best, strict=True)
            for pickup in chosen
        ]
