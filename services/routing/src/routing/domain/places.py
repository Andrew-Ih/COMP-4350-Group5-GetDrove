"""Places found by typing an address (#257, ADR 0027)."""

from dataclasses import dataclass

from routing.domain.values import LatLng

# Most matches a search returns, best first.
MAX_PLACES = 5


@dataclass(frozen=True)
class Area:
    """A rectangle on the map, in degrees."""

    west: float
    south: float
    east: float
    north: float

    def contains(self, point: LatLng) -> bool:
        return self.south <= point.lat <= self.north and self.west <= point.lng <= self.east


# The area our routing engine's map covers: BBOX in infra/osrm/Dockerfile. A place outside it
# couldn't be routed to, so it's never offered.
MAP_AREA = Area(west=-97.45, south=49.70, east=-96.85, north=50.05)


@dataclass(frozen=True)
class Place:
    """A match for what someone typed: a short label to choose by, and where it is."""

    label: str
    point: LatLng


def normalize_query(query: str) -> str:
    """The same search however it was typed: spaces collapsed, case ignored."""
    return " ".join(query.split()).casefold()
