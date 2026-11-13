"""Trip events persisted with the Trip transaction."""

from uuid import UUID

from events.catalog import SeatRequested, TripPosted
from events.outbox import OutboxPublisher
from trips.domain.entities import Trip
from trips.domain.seat_request import SeatRequest


class OutboxTripEvents:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self.publisher = publisher

    async def trip_posted(self, trip_id: UUID) -> None:
        await self.publisher.publish(TripPosted(trip_id=trip_id))

    async def seat_requested(self, request: SeatRequest, trip: Trip) -> None:
        await self.publisher.publish(
            SeatRequested(
                request_id=request.id,
                trip_id=request.trip_id,
                rider_id=request.rider_id,
                driver_id=trip.driver_id,
                departure_at=trip.departure_at,
            )
        )
