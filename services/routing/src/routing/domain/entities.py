"""Domain entities for the Routing service."""

from dataclasses import dataclass
from uuid import UUID

from routing.domain.values import LatLng


@dataclass(frozen=True)
class Route:
    """A trip's driving route: the road path from its origin to its destination."""

    trip_id: UUID
    path: tuple[LatLng, ...]
    distance_meters: int
    duration_seconds: int

    def __post_init__(self) -> None:
        """Validate the route's business rules."""

        if len(self.path) < 2:
            raise ValueError("A route needs at least two points")

        if self.distance_meters < 0:
            raise ValueError("Distance cannot be negative")

        if self.duration_seconds < 0:
            raise ValueError("Duration cannot be negative")
