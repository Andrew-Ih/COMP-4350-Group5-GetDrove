"""Trip events persisted with the Trip transaction."""

from uuid import UUID

from events.catalog import TripPosted
from events.outbox import OutboxPublisher


class OutboxTripEvents:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self.publisher = publisher

    async def trip_posted(self, trip_id: UUID) -> None:
        await self.publisher.publish(TripPosted(trip_id=trip_id))
