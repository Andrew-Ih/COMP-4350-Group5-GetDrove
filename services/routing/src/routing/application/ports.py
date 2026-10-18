"""Interfaces used by Routing application use cases."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from routing.domain.entities import Route
from routing.domain.values import LatLng


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
    async def save(self, route: Route) -> None:
        """Store the route, replacing the trip's existing route if it has one."""
        ...

    async def get(self, trip_id: UUID) -> Route | None:
        """The trip's route, or None if it has none."""
        ...
