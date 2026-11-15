"""Interfaces used by Trips application use cases."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from trips.domain.entities import Trip
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


class TripCancellationRepository(Protocol):
    async def get_for_update(self, trip_id: UUID) -> Trip | None: ...

    async def save_cancellation(self, trip: Trip, cancelled_at: datetime) -> list[UUID]:
        """Persist the cancellation and return the riders whose requests were closed."""
        ...


class TripCancellationEvents(Protocol):
    async def trip_cancelled(self, trip: Trip, rider_ids: list[UUID]) -> None: ...

    async def driver_late_cancellation(self, trip: Trip, cancelled_at: datetime) -> None: ...


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
