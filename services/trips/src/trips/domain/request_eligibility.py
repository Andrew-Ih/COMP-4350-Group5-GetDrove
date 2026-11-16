"""Eligibility rules for creating a seat request.

Database and external-service lookups supply the facts.
This module performs no I/O and changes no state.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trips.domain.entities import Trip
from trips.domain.request_errors import (
    AlreadyRequestedError,
    CardRequiredError,
    OverlappingRequestError,
    OwnTripError,
    TripFullError,
    TripNotFoundError,
    TripNotOpenError,
)
from trips.domain.values import TripStatus


@dataclass(frozen=True)
class RequestEligibility:
    trip: Trip | None
    rider_id: UUID
    now: datetime
    already_requested: bool
    overlapping_request: bool
    has_card: bool


def ensure_request_eligible(facts: RequestEligibility) -> None:
    """Raise the first applicable eligibility error, or return normally."""
    if facts.now.tzinfo is None or facts.now.utcoffset() is None:
        raise ValueError("Current time must include a timezone")

    trip = facts.trip

    if trip is None:
        raise TripNotFoundError("No trip exists with this ID.")

    if trip.driver_id == facts.rider_id:
        raise OwnTripError("You cannot request a seat on your own trip.")

    if trip.status != TripStatus.SCHEDULED or trip.departure_at <= facts.now:
        raise TripNotOpenError("This trip is no longer open for seat requests.")

    if facts.already_requested:
        raise AlreadyRequestedError("You already have a pending or accepted request on this trip.")

    if facts.overlapping_request:
        raise OverlappingRequestError(
            "Another pending or accepted request overlaps with this trip."
        )

    if trip.seats_available <= 0:
        raise TripFullError("This trip has no seats remaining.")

    if not facts.has_card:
        raise CardRequiredError("Add a payment card before requesting a seat.")
