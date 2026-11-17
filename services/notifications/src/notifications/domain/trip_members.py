"""Who is on a trip (#146): the driver, and the riders who have a seat. Notifications keeps
its own copy from Trips' events, so it never has to ask Trips."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class TripRole(StrEnum):
    DRIVER = "driver"
    RIDER = "rider"


@dataclass(frozen=True)
class TripMember:
    trip_id: UUID
    user_id: UUID
    role: TripRole
    active: bool = True  # False once a rider cancels or is removed, or the trip is cancelled
