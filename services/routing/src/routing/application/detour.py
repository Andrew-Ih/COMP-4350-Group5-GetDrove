"""Application use case for the extra driving time a new pickup adds to a trip (#36, #37).

Called by Trips when a seat is requested. The driver starts at the route's first point and
ends at its last; the accepted pickups sit between them in pickup order.

The drive times between those points (the "plan") are kept per exact list of points. A
quote that finds its plan only asks OSRM for the new pickup's row and column. Because the
key is the points themselves, a plan can't be stale: when the accepted pickups change, the
key does too.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from routing.application.ports import DetourPlanCache, DrivingMatrix, RouteRepository
from routing.domain.errors import RouteNotFoundError
from routing.domain.insertion import cheapest_insertion
from routing.domain.values import LatLng

type Matrix = list[list[float]]


@dataclass(frozen=True)
class Detour:
    added_seconds: int
    position: int
    total_seconds: int


def plan_key(points: Sequence[LatLng]) -> str:
    """The same points in the same order always give the same key; nothing else does."""
    text = ";".join(f"{point.lat!r},{point.lng!r}" for point in points)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _without_new(full: Matrix, slot: int) -> Matrix:
    keep = [i for i in range(len(full)) if i != slot]
    return [[full[i][j] for j in keep] for i in keep]


def _with_new(
    base: Matrix, from_new: Sequence[float], to_new: Sequence[float], slot: int
) -> Matrix:
    """The plan with the new pickup added at index ``slot``: the end moves up one."""
    size = len(base) + 1
    where = [i if i < slot else i + 1 for i in range(len(base))]
    full = [[0.0] * size for _ in range(size)]
    for a, i in enumerate(where):
        for b, j in enumerate(where):
            full[i][j] = base[a][b]
        full[i][slot] = to_new[a]
        full[slot][i] = from_new[a]
    return full


class DetourCost:
    def __init__(
        self, repository: RouteRepository, driving: DrivingMatrix, plans: DetourPlanCache
    ) -> None:
        self.repository = repository
        self.driving = driving
        self.plans = plans

    async def execute(
        self, trip_id: UUID, accepted_pickups: Sequence[LatLng], new_pickup: LatLng
    ) -> Detour:
        ends = await self.repository.route_ends(trip_id)
        if ends is None:
            raise RouteNotFoundError()
        start, end = ends

        count = len(accepted_pickups)
        slot = count + 1  # the new pickup's place in the order cheapest_insertion expects
        plan_points = [start, *accepted_pickups, end]
        key = plan_key(plan_points)

        base = await self.plans.get(trip_id, key)
        if base is not None and (
            len(base) != count + 2 or any(len(row) != count + 2 for row in base)
        ):
            base = None  # not a plan for these points: ignore it

        if base is None:
            full = await self.driving.durations([start, *accepted_pickups, new_pickup, end])
            base = _without_new(full, slot)
            await self.plans.put(trip_id, key, base)
        else:
            from_new, to_new = await self.driving.durations_around(new_pickup, plan_points)
            full = _with_new(base, from_new, to_new, slot)

        best = cheapest_insertion(full, count)

        # The trip as it stands: start, the accepted pickups, end.
        without_new = sum(base[i][i + 1] for i in range(count + 1))
        return Detour(
            added_seconds=round(best.added_seconds),
            position=best.position,
            total_seconds=round(without_new + best.added_seconds),
        )
