"""Value types shared by the Trips domain and its API."""

from dataclasses import dataclass
from enum import StrEnum


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
