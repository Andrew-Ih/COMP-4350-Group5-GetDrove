"""Value types shared by the Trips domain and its API."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class Direction(StrEnum):
    """Every trip goes to the Fort Garry campus or leaves from it."""

    TO_CAMPUS = "to_campus"
    FROM_CAMPUS = "from_campus"


class TripStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Location:
    label: str
    lat: float
    lng: float


# The campus end of every trip.
CAMPUS = Location(label="University of Manitoba, Fort Garry campus", lat=49.8075, lng=-97.1366)


def trip_ends(
    direction: Direction,
    place: Location,
) -> tuple[Location, Location]:
    """Determine a trip's origin and destination."""
    if direction == Direction.TO_CAMPUS:
        return place, CAMPUS
    if direction == Direction.FROM_CAMPUS:
        return CAMPUS, place
    raise ValueError("Invalid trip direction")


# ---------------------------------------------------------------- search (#97)


@dataclass(frozen=True)
class Point:
    """A bare location, like the rider's when searching: no label, never stored."""

    lat: float
    lng: float


# How far either side of the rider's time a trip can be.
SEARCH_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class SearchWindow:
    """Which trips fit the rider's time. Going to campus, the rider says when they want to
    arrive: trips arriving in the hour before it. Leaving campus, when they want to leave:
    trips leaving in the hour after it. Both ends are included."""

    direction: Direction
    start: datetime
    end: datetime
    by_arrival: bool  # True: compare estimated arrival; False: compare departure

    @classmethod
    def for_rider(cls, direction: Direction, time: datetime) -> "SearchWindow":
        if time.tzinfo is None or time.utcoffset() is None:
            raise ValueError("Search time must include a timezone")
        if direction == Direction.TO_CAMPUS:
            return cls(direction, time - SEARCH_WINDOW, time, by_arrival=True)
        return cls(direction, time, time + SEARCH_WINDOW, by_arrival=False)


@dataclass(frozen=True)
class TripMatch:
    """Routing's answer for a trip the rider can walk to. ``pickup`` is where the rider gets
    in going to campus, and out leaving it."""

    trip_id: UUID
    pickup: Location
    walk_seconds: int
    meters_to_trip_end: int  # along the route, from the pickup to the end of the trip


def ride_meters(direction: Direction, trip_distance_meters: int, match: TripMatch) -> int:
    """How far the rider rides, which their share is priced on. Going to campus they ride
    from the pickup to the end; leaving campus, from the start (campus) to the drop-off."""
    if direction == Direction.TO_CAMPUS:
        return match.meters_to_trip_end
    return max(0, trip_distance_meters - match.meters_to_trip_end)


@dataclass(frozen=True)
class Quote:
    """Payments' price for the rider's share."""

    amount_cents: int
    currency: str
    explanation: str
