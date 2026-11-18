"""Saved rider shares and provider references, independent of Stripe and HTTP."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID

FailureReason = Literal["card_declined", "authentication_required", "no_card", "other"]


class HoldStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    RELEASED = "RELEASED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SavedPaymentCard:
    customer_id: str
    payment_method_id: str


@dataclass(frozen=True)
class PaymentHold:
    request_id: UUID
    trip_id: UUID
    rider_id: UUID
    driver_id: UUID
    amount_cents: int
    currency: Literal["CAD"]
    departure_at: datetime
    authorize_at: datetime
    status: HoldStatus = HoldStatus.SCHEDULED
    stripe_id: str | None = None
    release_requested: bool = False
    card: SavedPaymentCard | None = None
    first_attempt_at: datetime | None = None
    correlation_id: str | None = None
    # None on a scheduled hold means manual reconciliation is required, not retry forever.
    retry_at: datetime | None = None

    def needs_card(self, now: datetime) -> bool:
        return (
            self.status is HoldStatus.SCHEDULED
            and not self.release_requested
            and self.card is None
            and self.retry_at is not None
            and self.authorize_at <= now
            and self.retry_at <= now
            and now < self.departure_at
        )

    def __post_init__(self) -> None:
        if self.amount_cents <= 0 or self.currency != "CAD":
            raise ValueError("A hold requires a positive CAD amount")


def authorization_time(accepted_at: datetime, departure_at: datetime) -> datetime:
    """Far-ahead bookings wait until the day before departure (#154)."""
    if departure_at - accepted_at > timedelta(days=6):
        return departure_at - timedelta(hours=24)
    return accepted_at
