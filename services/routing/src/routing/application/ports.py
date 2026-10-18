"""Interfaces used by Routing application use cases."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from routing.domain.entities import Route
from routing.domain.values import Corridor, CorridorHit, LatLng, RouteSample


@dataclass(frozen=True)
class DrivingRoute:
    """What the routing engine returns for a drive between two points."""

    path: tuple[LatLng, ...]
    distance_meters: int
    duration_seconds: int


class RoutingEngine(Protocol):
    async def driving_route(self, origin: LatLng, destination: LatLng) -> DrivingRoute:
        """Raise NoRouteError if there's no road route, RoutingEngineUnavailableError if the
        engine is down or too slow."""
        ...


class RouteRepository(Protocol):
    async def save(self, route: Route, samples: Sequence[RouteSample]) -> None:
        """Store the route and its samples, replacing the trip's existing ones if it has
        any."""
        ...

    async def get(self, trip_id: UUID) -> Route | None:
        """The trip's route, or None if it has none."""
        ...

    async def samples_in_corridor(
        self, rider: LatLng, trip_ids: Sequence[UUID], corridor: Corridor
    ) -> list[CorridorHit]:
        """Samples of these trips' routes within the corridor's radius of the rider, in a
        straight line: a quick first pass before checking walking times (#26). Ordered by
        trip, then nearest first. Trips with no sample in the corridor are left out."""
        ...
