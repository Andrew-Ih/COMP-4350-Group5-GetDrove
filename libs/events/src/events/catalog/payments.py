"""Events published by the Payments service, on the ``events.payments`` stream."""

from typing import ClassVar, Literal
from uuid import UUID

from pydantic import Field

from events.envelope import EventPayload

PaymentFailureReason = Literal["card_declined", "authentication_required", "no_card", "other"]


class PaymentHeld(EventPayload):
    """The rider's share is held on their card, ready to be charged after the trip (#70).
    No consumers yet."""

    event_type: ClassVar[str] = "PaymentHeld"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    amount_cents: int = Field(ge=0)
    currency: Literal["CAD"] = "CAD"


class PaymentFailed(EventPayload):
    """The hold couldn't be placed (#153).

    Consumers: Trips (marks the request ``payment_failed`` and frees the seat), Notifications
    (tells the rider what to do).
    """

    event_type: ClassVar[str] = "PaymentFailed"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    reason: PaymentFailureReason


class PaymentReleased(EventPayload):
    """A hold was cancelled because the ride won't happen (#72). No consumers yet."""

    event_type: ClassVar[str] = "PaymentReleased"
    event_version: ClassVar[int] = 1

    request_id: UUID
    trip_id: UUID
    rider_id: UUID
