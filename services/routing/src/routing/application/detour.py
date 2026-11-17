"""Application use case for the extra driving time a new pickup adds to a trip (#36).

Called by Trips when a seat is requested. The trip's driver starts at the route's first
point and ends at its last; the accepted pickups sit between them in pickup order.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from uuid import UUID

from routing.application.ports import DrivingMatrix, RouteRepository
from routing.domain.errors import RouteNotFoundError
from routing.domain.insertion import cheapest_insertion
from routing.domain.values import LatLng


@dataclass(frozen=True)
class Detour:
    added_seconds: int
    position: int
    total_seconds: int


class DetourCost:
    def __init__(self, repository: RouteRepository, driving: DrivingMatrix) -> None:
        self.repository = repository
        self.driving = driving

    async def execute(
        self, trip_id: UUID, accepted_pickups: Sequence[LatLng], new_pickup: LatLng
    ) -> Detour:
        route = await self.repository.get(trip_id)
        if route is None:
            raise RouteNotFoundError()

        # The order cheapest_insertion expects: start, accepted pickups, new pickup,
        # destination.
        stops = [route.path[0], *accepted_pickups, new_pickup, route.path[-1]]
        count = len(accepted_pickups)
        durations = await self.driving.durations(stops)

        best = cheapest_insertion(durations, count)

        # The trip as it stands, without the new pickup: start, the accepted pickups,
        # destination (the new pickup is the second to last point).
        current = [*range(count + 1), count + 2]
        without_new = sum(durations[a][b] for a, b in pairwise(current))
        return Detour(
            added_seconds=round(best.added_seconds),
            position=best.position,
            total_seconds=round(without_new + best.added_seconds),
        )
