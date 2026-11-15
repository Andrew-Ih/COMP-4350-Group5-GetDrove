"""Trip events persisted with the Trip transaction."""

from datetime import datetime
from uuid import UUID

from events.catalog import DriverLateCancellation, TripCancelled, TripPosted
from events.outbox import OutboxPublisher
from trips.domain.entities import Trip


class OutboxTripEvents:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self.publisher = publisher

    async def trip_posted(self, trip_id: UUID) -> None:
        await self.publisher.publish(TripPosted(trip_id=trip_id))

    async def trip_cancelled(self, trip: Trip, rider_ids: list[UUID]) -> None:
        await self.publisher.publish(
            TripCancelled(
                trip_id=trip.id,
                driver_id=trip.driver_id,
                series_id=None,
                departure_at=trip.departure_at,
                rider_ids=rider_ids,
            )
        )

    async def driver_late_cancellation(self, trip: Trip, cancelled_at: datetime) -> None:
        await self.publisher.publish(
            DriverLateCancellation(
                trip_id=trip.id,
                driver_id=trip.driver_id,
                departure_at=trip.departure_at,
                cancelled_at=cancelled_at,
            )
        )
