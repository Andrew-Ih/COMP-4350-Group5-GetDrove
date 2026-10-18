"""Application use case for finding the trips a rider can walk to (#26).

1. The corridor (#25): samples of the candidate trips' routes within a straight-line radius
   of the rider. Quick, but a river or a highway can be in the way.
2. The real check: the walking time from the rider to those samples, along paths and
   sidewalks. A trip matches only if some sample is close enough on foot.
3. Per matching trip, the sample with the shortest walk is the point offered to the rider.

Samples near either end of a route are never offered. One end is campus; the other is the
driver's own place, usually near home, which riders must not be able to find (a pickup
pin a few meters from it would give it away). "Near" is in a straight line, not along the
route: leaving a cul-de-sac, 300 m of road can end up a few houses from where it started.

The point is where the rider is picked up going to campus, and dropped off leaving it.
``rider_distance_meters`` is always the rest of the route from that point; Trips knows the
direction, and works out how far the rider actually rides.

The rider's location is used for the calculation only, never stored or logged.
"""

import asyncio
from collections.abc import Sequence
from uuid import UUID

from routing.application.ports import RouteRepository, RoutingEngine, WalkingEngine
from routing.domain.values import Corridor, CorridorHit, LatLng, RiderMatch, Walk

# Nearest samples per trip whose walking time is checked: 800 m either side of the rider at
# 100 m spacing is about 17, so this keeps a whole pass of the route.
SAMPLES_PER_TRIP = 20

# Samples this close to either end of a route, in a straight line, are never offered.
PRIVATE_END_METERS = 300

# When no road nearby has a name (a parking lot, a service road). Read after "Pickup at"
# and "5 min walk to".
DEFAULT_PICKUP_LABEL = "a spot on the driver's route"


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

        hits = _nearest_per_trip(
            [
                hit
                for hit in await self.repository.samples_in_corridor(rider, trip_ids, self.corridor)
                if _away_from_the_ends(hit)
            ]
        )
        if not hits:
            return []

        walks = await self.walking.walks(rider, [hit.sample.point for hit in hits])

        best: dict[UUID, tuple[CorridorHit, Walk]] = {}
        for hit, walk in zip(hits, walks, strict=True):
            if walk is None or walk.seconds > self.max_walk_seconds:
                continue
            current = best.get(hit.trip_id)
            if current is None or walk.seconds < current[1].seconds:
                best[hit.trip_id] = (hit, walk)

        # In the order Trips asked, without repeats.
        matched = [trip_id for trip_id in dict.fromkeys(trip_ids) if trip_id in best]
        names = await asyncio.gather(
            *(self.driving.road_name(best[trip_id][0].sample.point) for trip_id in matched)
        )

        return [
            RiderMatch(
                trip_id=trip_id,
                pickup=best[trip_id][0].sample.point,
                pickup_label=name or DEFAULT_PICKUP_LABEL,
                walk_seconds=best[trip_id][1].seconds,
                rider_distance_meters=best[trip_id][0].remaining_meters,
            )
            for trip_id, name in zip(matched, names, strict=True)
        ]


def _away_from_the_ends(hit: CorridorHit) -> bool:
    return hit.from_ends_meters >= PRIVATE_END_METERS


def _nearest_per_trip(hits: list[CorridorHit]) -> list[CorridorHit]:
    """The first SAMPLES_PER_TRIP hits of each trip (hits come nearest first per trip)."""
    kept: list[CorridorHit] = []
    counts: dict[UUID, int] = {}
    for hit in hits:
        if counts.get(hit.trip_id, 0) < SAMPLES_PER_TRIP:
            counts[hit.trip_id] = counts.get(hit.trip_id, 0) + 1
            kept.append(hit)
    return kept
