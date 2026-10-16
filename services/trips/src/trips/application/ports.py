"""Interfaces used by Trips application use cases."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from trips.domain.entities import Trip
from trips.domain.values import Location


class TripRepository(Protocol):
    async def add(self, trip: Trip) -> None: ...


class TripEvents(Protocol):
    async def trip_posted(self, trip_id: UUID) -> None:
        """Record TripPosted in the same transaction as the Trip."""
        ...


@dataclass(frozen=True)
class RouteEstimate:
    distance_meters: int
    duration_seconds: int


class RoutingService(Protocol):
    async def compute_route(
        self,
        trip_id: UUID,
        origin: Location,
        destination: Location,
    ) -> RouteEstimate: ...
