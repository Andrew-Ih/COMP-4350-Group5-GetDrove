"""Business rules for detecting overlapping trips."""

from datetime import datetime

from trips.domain.entities import Trip


def has_trip_conflict(
    departure_at: datetime,
    estimated_arrival_at: datetime,
    existing_trips: list[Trip],
) -> bool:
    """Check whether a proposed trip overlaps an existing trip."""

    return any(
        departure_at < trip.estimated_arrival_at and trip.departure_at < estimated_arrival_at
        for trip in existing_trips
    )
