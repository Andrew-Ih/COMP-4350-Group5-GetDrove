"""Events published by the Trips service, on the ``events.trips`` stream."""

from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import Field

from events.envelope import EventPayload


class TripPosted(EventPayload):
    """A trip was posted. Published on the events.trips stream."""

    event_type: ClassVar[str] = "TripPosted"
    event_version: ClassVar[int] = 1

    # Do not include private driver locations in this event.
    trip_id: UUID


class SeatRequested(EventPayload):
    """A rider asked for a seat and the request is waiting for the driver (#137).

    Not published for a request that was auto-accepted straight away: that one publishes
    ``RequestAccepted`` instead. Consumers: Notifications (tells the driver).
    """

    event_type: ClassVar[str] = "SeatRequested"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    driver_id: UUID
    departure_at: datetime


class RequestAccepted(EventPayload):
    """The driver accepted a request, or auto-accept did (#138, #43).

    Consumers: Payments (holds ``amountCents`` on the rider's card, #70), Notifications
    (tells the rider and schedules their reminder, #146, #148).
    """

    event_type: ClassVar[str] = "RequestAccepted"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    driver_id: UUID
    departure_at: datetime
    pickup_label: str = Field(description="Where the rider is picked up, for the reminder.")
    amount_cents: int = Field(
        ge=0, description="The rider's share saved when they requested (#69). Never recalculated."
    )
    currency: Literal["CAD"] = "CAD"
    auto_accepted: bool


class RequestDeclined(EventPayload):
    """The driver declined a request, pending or already accepted (#138).

    Consumers: Payments (releases the hold if there was one, #72), Notifications.
    """

    event_type: ClassVar[str] = "RequestDeclined"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    driver_id: UUID
    was_accepted: bool = Field(description="True if the rider had a seat (and maybe a hold).")


class RequestCancelled(EventPayload):
    """The rider cancelled their request, pending or accepted (#138).

    Consumers: Payments (releases the hold if there was one, #72), Notifications (tells the
    driver and cancels the rider's reminder, #146, #148).
    """

    event_type: ClassVar[str] = "RequestCancelled"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    driver_id: UUID
    was_accepted: bool = Field(description="True if the rider had a seat (and maybe a hold).")


class TripCancelled(EventPayload):
    """The driver cancelled a trip before it started (#132, #18).

    Consumers: Payments (releases every hold on the trip, #72), Notifications (tells the
    riders and cancels their reminders), Routing (forgets the route).
    """

    event_type: ClassVar[str] = "TripCancelled"
    event_version: ClassVar[int] = 1

    trip_id: UUID
    driver_id: UUID
    series_id: UUID | None = Field(description="Set when the trip is part of a recurring series.")
    departure_at: datetime
    rider_ids: list[UUID] = Field(
        description="Riders who had a pending or accepted request on the trip."
    )


class DriverLateCancellation(EventPayload):
    """A trip was cancelled less than one hour before departure (#132). Published alongside
    ``TripCancelled``. Consumers: Accounts (the driver's reliability record, Sprint 3, #134).
    """

    event_type: ClassVar[str] = "DriverLateCancellation"
    event_version: ClassVar[int] = 1

    trip_id: UUID
    driver_id: UUID
    departure_at: datetime
    cancelled_at: datetime
