"""Routing interface used when creating a seat request."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from trips.domain.values import Location, Point


@dataclass(frozen=True)
class SelectedPickup:
    id: str
    location: Location
    walk_seconds: int
    meters_to_trip_end: int


@dataclass(frozen=True)
class DetourEstimate:
    added_seconds: int
    position: int
    total_seconds: int


class RequestRoutingService(Protocol):
    async def select_pickup(
        self,
        *,
        trip_id: UUID,
        rider: Point,
        pickup_id: str,
    ) -> SelectedPickup:
        """Validate the selected ID against Routing's current pickup options."""
        ...

    async def estimate_detour(
        self,
        *,
        trip_id: UUID,
        accepted_pickups: Sequence[Location],
        new_pickup: Location,
    ) -> DetourEstimate:
        """Calculate insertion position and extra driving time."""
        ...
