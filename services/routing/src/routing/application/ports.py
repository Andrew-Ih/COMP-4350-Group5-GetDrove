"""Interfaces used by Routing application use cases."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from routing.domain.entities import Route
from routing.domain.values import Corridor, CorridorHit, LatLng, RouteSample, Walk


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

    async def road_name(self, point: LatLng) -> str | None:
        """The name of the drivable road nearest the point, for pickup labels. None if it
        has no name or the engine can't say: a label is never worth failing a request."""
        ...


class DrivingMatrix(Protocol):
    async def durations(self, points: Sequence[LatLng]) -> list[list[float]]:
        """Drive time in seconds from every point to every other, as a square matrix in
        the same order as ``points``: ``result[i][j]`` is point i to point j. Raise
        RoutingEngineUnavailableError if the engine is down or too slow, or if any pair
        has no route: a detour computed from a guess would be a wrong number."""
        ...

    async def durations_around(
        self, point: LatLng, others: Sequence[LatLng]
    ) -> tuple[list[float], list[float]]:
        """Drive time from ``point`` to each of ``others``, then from each of ``others`` to
        ``point``. Raise RoutingEngineUnavailableError as ``durations`` does."""
        ...


class DetourPlanCache(Protocol):
    """The duration matrix of a trip's start, accepted pickups and end (#37), by the exact
    points it was worked out for. A cache never fails a quote: errors are a miss."""

    async def get(self, trip_id: UUID, key: str) -> list[list[float]] | None: ...

    async def put(self, trip_id: UUID, key: str, matrix: list[list[float]]) -> None: ...

    async def forget(self, trip_id: UUID) -> None:
        """Drop every plan of the trip."""
        ...


class WalkingEngine(Protocol):
    async def walks(self, origin: LatLng, destinations: Sequence[LatLng]) -> list[Walk | None]:
        """The walk from ``origin`` to each destination, in the same order; None where
        there's no walking route. Raise RoutingEngineUnavailableError if the engine is down
        or too slow."""
        ...


class RouteRepository(Protocol):
    async def save(self, route: Route, samples: Sequence[RouteSample]) -> None:
        """Store the route and its samples, replacing the trip's existing ones if it has
        any."""
        ...

    async def get(self, trip_id: UUID) -> Route | None:
        """The trip's route, or None if it has none."""
        ...

    async def has_route(self, trip_id: UUID) -> bool:
        """Whether the trip has a stored route (cheaper than ``get``)."""
        ...

    async def samples_in_corridor(
        self, rider: LatLng, trip_ids: Sequence[UUID], corridor: Corridor
    ) -> list[CorridorHit]:
        """Samples of these trips' routes within the corridor's radius of the rider, in a
        straight line: a quick first pass before checking walking times (#26). Ordered by
        trip, then nearest first. Trips with no sample in the corridor are left out."""
        ...

    async def route_ends(self, trip_id: UUID) -> tuple[LatLng, LatLng] | None:
        """The first and last points of the trip's route, or None if it has none. Cheaper
        than ``get``: the rest of the path isn't read."""
        ...
