"""Choosing pickup points on a trip's route for a rider: shared by search (#26) and the
pickup points endpoint (#29), so a trip's suggested point is the same in both.

1. The corridor (#25): samples of the route within a straight-line radius of the rider.
2. Samples near either end of the route are never offered. One end is campus; the other is
   the driver's own place, usually near home, which riders must not be able to find (a
   pickup pin a few meters from it would give it away). "Near" is in a straight line, not
   along the route: leaving a cul-de-sac, 300 m of road can end up a few houses away.
3. The walking time from the rider to each sample, along paths and sidewalks. Samples the
   rider can't walk to within the limit are dropped: a river or a highway can be in the way.
4. Shortest walk first, skipping points on roads a driver can't stop on and points too close
   to one already chosen.

The point is where the rider is picked up going to campus, and dropped off leaving it.
``rider_distance_meters`` is always the rest of the route from that point; Trips knows the
direction, and works out how far the rider actually rides.

The rider's location is used for the calculation only, never stored or logged.
"""

from collections.abc import Sequence
from uuid import UUID

from routing.application.ports import RoutingEngine, WalkingEngine
from routing.domain.pickups import MIN_PICKUP_SPACING_METERS, is_excluded_road, pickup_id
from routing.domain.values import CorridorHit, LatLng, PickupCandidate, Walk

# Nearest samples per trip whose walking time is checked: 800 m either side of the rider at
# 100 m spacing is about 17, so this keeps a whole pass of the route.
SAMPLES_PER_TRIP = 20

# Samples this close to either end of a route, in a straight line, are never offered.
PRIVATE_END_METERS = 300

# When no road nearby has a name (a parking lot, a service road). Read after "Pickup at"
# and "5 min walk to".
DEFAULT_PICKUP_LABEL = "a spot on the driver's route"

type Reachable = list[tuple[CorridorHit, Walk]]


def offerable(hits: list[CorridorHit]) -> list[CorridorHit]:
    """Away from both ends of the route, and only each trip's nearest SAMPLES_PER_TRIP
    (hits come grouped by trip, nearest first)."""
    kept: list[CorridorHit] = []
    counts: dict[UUID, int] = {}
    for hit in hits:
        if hit.from_ends_meters < PRIVATE_END_METERS:
            continue
        if counts.get(hit.trip_id, 0) < SAMPLES_PER_TRIP:
            counts[hit.trip_id] = counts.get(hit.trip_id, 0) + 1
            kept.append(hit)
    return kept


async def walkable(
    rider: LatLng, hits: list[CorridorHit], walking: WalkingEngine, max_walk_seconds: int
) -> Reachable:
    """The hits the rider can walk to within the limit, with their walk, shortest first. One
    request to the walking engine for all of them."""
    if not hits:
        return []
    walks = await walking.walks(rider, [hit.sample.point for hit in hits])
    reachable = [
        (hit, walk)
        for hit, walk in zip(hits, walks, strict=True)
        if walk is not None and walk.seconds <= max_walk_seconds
    ]
    # Ties: the point further along the route first, for a steady order.
    return sorted(reachable, key=lambda pair: (pair[1].seconds, -pair[0].sample.offset_meters))


async def choose(
    reachable: Reachable, driving: RoutingEngine, limit: int, exclude: Sequence[str] = ()
) -> list[PickupCandidate]:
    """Up to ``limit`` pickup points from one trip's reachable samples (shortest walk first):
    never one the rider rejected (``exclude``, by ID), never on an excluded road, and spread
    out along the route, away from the ones offered and the ones rejected."""
    rejected = set(exclude)
    chosen: list[PickupCandidate] = []
    # A rejected point keeps its 200 m: the next suggestion is a different spot, not the
    # sample next door (which is what the rider just said no to).
    offsets = [
        hit.sample.offset_meters for hit, _ in reachable if pickup_id(hit.sample.seq) in rejected
    ]
    for hit, walk in reachable:
        if len(chosen) == limit:
            break
        offset = hit.sample.offset_meters
        if any(abs(offset - other) < MIN_PICKUP_SPACING_METERS for other in offsets):
            continue
        # Asked one at a time, in order: usually the first is fine, so it's one request.
        # This fails open: road_name is None both for an unnamed road and when the car
        # profile is down, so then excluded roads aren't recognised (see the README).
        name = await driving.road_name(hit.sample.point)
        if name is not None and is_excluded_road(name):
            continue
        chosen.append(
            PickupCandidate(
                id=pickup_id(hit.sample.seq),
                point=hit.sample.point,
                label=name or DEFAULT_PICKUP_LABEL,
                walk_seconds=walk.seconds,
                rider_distance_meters=hit.remaining_meters,
            )
        )
        offsets.append(offset)
    return chosen
