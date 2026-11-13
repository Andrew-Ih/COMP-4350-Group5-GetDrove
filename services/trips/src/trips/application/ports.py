"""Interfaces used by Trips application use cases."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from trips.domain.entities import Trip
from trips.domain.seat_request import SeatRequest
from trips.domain.values import Location, Point, Quote, SearchWindow, TripMatch


class TripRepository(Protocol):
    async def add(self, trip: Trip) -> None: ...

    async def search(
        self, window: SearchWindow, departs_after: datetime, exclude_driver_id: UUID
    ) -> list[Trip]:
        """Scheduled trips in this direction and time window, with a free seat, that haven't
        left yet, except the given driver's own."""
        ...

    async def get_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]: ...

    async def get(self, trip_id: UUID) -> Trip | None: ...


class TripEvents(Protocol):
    async def trip_posted(self, trip_id: UUID) -> None:
        """Record TripPosted in the same transaction as the Trip."""
        ...


@dataclass(frozen=True)
class RouteEstimate:
    distance_meters: int
    duration_seconds: int


class RoutingService(Protocol):
    async def compute_route(
        self,
        trip_id: UUID,
        origin: Location,
        destination: Location,
    ) -> RouteEstimate: ...

    async def match(self, rider: Point, trip_ids: Sequence[UUID]) -> list[TripMatch]:
        """The trips the rider can walk to, with a pickup point for each. Raise
        RoutingUnavailableError if Routing can't answer."""
        ...


class PricingService(Protocol):
    async def quote(self, distance_meters: int) -> Quote:
        """The rider's share for riding this far. Raise PricingUnavailableError if Payments
        can't answer."""
        ...


class RiderCardService(Protocol):
    async def has_card(self, rider_id: UUID) -> bool:
        """Return saved-card status.

        Raise CardStatusUnavailableError if the status cannot be determined.
        """
        ...


class SeatRequestRepository(Protocol):
    async def add(self, request: SeatRequest) -> None: ...

    async def get(self, request_id: UUID) -> SeatRequest | None: ...

    async def get_active_for_trip(self, trip_id: UUID, rider_id: UUID) -> SeatRequest | None:
        """The rider's pending or accepted request on this trip, if any."""
        ...

    async def has_overlapping_active_request(
        self, rider_id: UUID, starts_at: datetime, ends_at: datetime
    ) -> bool:
        """Whether a pending or accepted request is on a trip overlapping this time."""
        ...

    async def list_accepted_pickups(self, trip_id: UUID) -> list[Location]: ...


class SeatRequestEvents(Protocol):
    async def seat_requested(self, request: SeatRequest, trip: Trip) -> None: ...
