"""Events published by the Trips service."""

from typing import ClassVar
from uuid import UUID

from events.envelope import EventPayload


class TripPosted(EventPayload):
    """A trip was posted. Published on the events.trips stream."""

    event_type: ClassVar[str] = "TripPosted"
    event_version: ClassVar[int] = 1

    # Do not include private driver locations in this event.
    trip_id: UUID
