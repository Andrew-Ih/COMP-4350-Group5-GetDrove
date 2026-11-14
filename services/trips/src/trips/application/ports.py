"""Interfaces used by Trips application use cases."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from trips.domain.entities import Trip
from trips.domain.values import (
    Direction,
    Location,
    PickupOffer,
    Point,
    Quote,
    SearchWindow,
    TripMatch,
)


class TripRepository(Protocol):
    async def add(self, trip: Trip) -> None: ...

    async def get(self, trip_id: UUID) -> Trip | None:
        """The trip, whatever its status, or None if there's no trip with this ID."""
        ...

    async def search(
        self, window: SearchWindow, departs_after: datetime, exclude_driver_id: UUID
    ) -> list[Trip]:
        """Scheduled trips in this direction and time window, with a free seat, that haven't
        left yet, except the given driver's own."""
        ...

    async def get_upcoming_by_driver(self, driver_id: UUID, now: datetime) -> list[Trip]: ...


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
        driver_id: UUID,
        direction: Direction,
    ) -> RouteEstimate:
        """``driver_id`` and ``direction`` let Routing show the whole route to the driver
        only, and hide the driver's own end from everyone else (#135)."""
        ...

    async def match(self, rider: Point, trip_ids: Sequence[UUID]) -> list[TripMatch]:
        """The trips the rider can walk to, with a pickup point for each. Raise
        RoutingUnavailableError if Routing can't answer."""
        ...

    async def pickup_points(
        self, trip_id: UUID, rider: Point, limit: int, exclude: Sequence[str]
    ) -> list[PickupOffer]:
        """Up to ``limit`` pickup points on the trip's route for the rider, best first, never
        one in ``exclude`` (#29). Empty if the route doesn't pass within walking distance, or
        the trip has no route. Raise RoutingUnavailableError if Routing can't answer."""
        ...


class PricingService(Protocol):
    async def quote(self, distance_meters: int) -> Quote:
        """The rider's share for riding this far. Raise PricingUnavailableError if Payments
        can't answer."""
        ...
