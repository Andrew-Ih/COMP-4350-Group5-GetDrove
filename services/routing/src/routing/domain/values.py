"""Value types for the Routing domain."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class LatLng:
    """A point on the map (WGS 84)."""

    lat: float
    lng: float


@dataclass(frozen=True)
class RouteSample:
    """A point on a route, from points spaced evenly along it (#25).

    ``offset_meters`` and ``offset_seconds`` say how far into the drive it is, so a rider
    picked up here rides ``distance_meters - offset_meters`` of the route.
    """

    seq: int
    point: LatLng
    offset_meters: int
    offset_seconds: int


@dataclass(frozen=True)
class Corridor:
    """The area within ``radius_meters`` (straight line) of a route."""

    radius_meters: int

    def __post_init__(self) -> None:
        if self.radius_meters <= 0:
            raise ValueError("Corridor radius must be positive")


@dataclass(frozen=True)
class CorridorHit:
    """A sample on a trip's route that lies inside the corridor around a rider."""

    trip_id: UUID
    sample: RouteSample
    distance_meters: int  # straight line from the rider
    remaining_meters: int  # along the route, from this sample to the trip's end


@dataclass(frozen=True)
class Walk:
    """How long a walk takes on foot, along paths and sidewalks."""

    seconds: int
    meters: int


@dataclass(frozen=True)
class RiderMatch:
    """A trip the rider can walk to, with the best place on its route to be picked up (#26)."""

    trip_id: UUID
    pickup: LatLng
    pickup_label: str
    walk_seconds: int
    rider_distance_meters: int  # in the car, from the pickup to the trip's end
