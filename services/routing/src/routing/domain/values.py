"""Value types for the Routing domain."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LatLng:
    """A point on the map (WGS 84)."""

    lat: float
    lng: float
