"""Privacy-preserving TripPosted events, persisted with the Trip transaction."""

from typing import ClassVar
from uuid import UUID

from events.envelope import EventPayload
from events.outbox import OutboxPublisher


class TripPosted(EventPayload):
    """Published on events.trips; private locations never leave Trips in this event."""

    event_type: ClassVar[str] = "TripPosted"
    trip_id: UUID


class OutboxTripEvents:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self.publisher = publisher

    async def trip_posted(self, trip_id: UUID) -> None:
        await self.publisher.publish(TripPosted(trip_id=trip_id))
