"""Application use case for the pickup points offered to a rider on one trip (#29).

Called by Trips for the trip detail and when a seat is requested. The first point is the
same one search offered for this trip and spot (both use ``routing.application.pickups``).
"""

from collections.abc import Sequence
from uuid import UUID

from routing.application.pickups import choose, offerable, walkable
from routing.application.ports import RouteRepository, RoutingEngine, WalkingEngine
from routing.domain.errors import RouteNotFoundError
from routing.domain.values import Corridor, LatLng, PickupCandidate


class SuggestPickups:
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

    async def execute(
        self, trip_id: UUID, rider: LatLng, limit: int, exclude: Sequence[str] = ()
    ) -> list[PickupCandidate]:
        """``exclude``: IDs of points the rider rejected (#136). They're never returned, so
        the next best come back instead; unknown IDs are ignored."""
        if not await self.repository.has_route(trip_id):
            raise RouteNotFoundError()

        hits = offerable(await self.repository.samples_in_corridor(rider, [trip_id], self.corridor))
        reachable = await walkable(rider, hits, self.walking, self.max_walk_seconds)
        return await choose(reachable, self.driving, limit, exclude)
