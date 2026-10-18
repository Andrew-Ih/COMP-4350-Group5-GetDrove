"""Domain entities for the Trips service."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID, uuid4

from trips.domain.values import Direction, Location, TripStatus, trip_ends


@dataclass
class Trip:
    id: UUID
    driver_id: UUID
    direction: Direction
    origin: Location
    destination: Location
    departure_at: datetime
    estimated_arrival_at: datetime
    duration_seconds: int
    distance_meters: int
    seats_total: int
    seats_available: int
    status: TripStatus

    def __post_init__(self) -> None:
        """Validate the trip's business rules."""

        if not 1 <= self.seats_total <= 6:
            raise ValueError("Seats must be between 1 and 6")

        if not 0 <= self.seats_available <= self.seats_total:
            raise ValueError("Invalid seat availability")

        if self.duration_seconds < 0:
            raise ValueError("Duration cannot be negative")

        if self.distance_meters < 0:
            raise ValueError("Distance cannot be negative")

        if self.departure_at.tzinfo is None or self.departure_at.utcoffset() is None:
            raise ValueError("Departure time must include a timezone")

        if (
            self.estimated_arrival_at.tzinfo is None
            or self.estimated_arrival_at.utcoffset() is None
        ):
            raise ValueError("Arrival time must include a timezone")

        if self.estimated_arrival_at < self.departure_at:
            raise ValueError("Arrival cannot be before departure")

    @classmethod
    def create(
        cls,
        driver_id: UUID,
        direction: Direction,
        place: Location,
        departure_at: datetime,
        duration_seconds: int,
        distance_meters: int,
        seats_total: int,
        trip_id: UUID | None = None,
    ) -> Self:
        """Create a new scheduled trip."""

        origin, destination = trip_ends(direction, place)

        if departure_at.tzinfo is None or departure_at.utcoffset() is None:
            raise ValueError("Departure time must include a timezone")

        estimated_arrival_at = departure_at + timedelta(seconds=duration_seconds)

        return cls(
            id=trip_id if trip_id is not None else uuid4(),
            driver_id=driver_id,
            direction=direction,
            origin=origin,
            destination=destination,
            departure_at=departure_at,
            estimated_arrival_at=estimated_arrival_at,
            duration_seconds=duration_seconds,
            distance_meters=distance_meters,
            seats_total=seats_total,
            seats_available=seats_total,
            status=TripStatus.SCHEDULED,
        )

    def cancel(self) -> None:
        self.status = TripStatus.CANCELLED
