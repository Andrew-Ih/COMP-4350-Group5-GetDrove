"""Application use case for posting a one-off trip."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from trips.application.ports import RoutingService, TripEvents, TripRepository
from trips.domain.entities import Trip
from trips.domain.errors import DepartureInPastError
from trips.domain.values import Direction, Location, trip_ends


class PostTrip:
    def __init__(
        self,
        repository: TripRepository,
        routing: RoutingService,
        events: TripEvents,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.routing = routing
        self.events = events
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        driver_id: UUID,
        direction: Direction,
        place: Location,
        departure_at: datetime,
        seats_total: int,
    ) -> Trip:
        if (
            departure_at.tzinfo is None
            or departure_at.utcoffset() is None
            or departure_at <= self.clock()
        ):
            raise DepartureInPastError()

        trip_id = uuid4()

        origin, destination = trip_ends(direction, place)

        route = await self.routing.compute_route(
            trip_id=trip_id,
            origin=origin,
            destination=destination,
        )

        trip = Trip.create(
            driver_id=driver_id,
            direction=direction,
            place=place,
            departure_at=departure_at,
            duration_seconds=route.duration_seconds,
            distance_meters=route.distance_meters,
            seats_total=seats_total,
            trip_id=trip_id,
        )

        await self.repository.add(trip)
        await self.events.trip_posted(trip.id)

        return trip
