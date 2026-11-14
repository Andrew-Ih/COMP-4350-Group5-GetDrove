"""A rider's request for a seat, including the saved pickup and price quote."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from trips.domain.request_errors import (
    RequestNotCancellableError,
    RequestNotDecidableError,
    RequestNotPendingError,
)
from trips.domain.values import Location, Quote


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAYMENT_FAILED = "payment_failed"


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True)
class SeatRequest:
    id: UUID
    trip_id: UUID
    rider_id: UUID
    pickup: Location
    walk_seconds: int
    rider_distance_meters: int
    detour_seconds: int | None
    cost: Quote
    status: RequestStatus
    auto_accepted: bool
    created_at: datetime
    decided_at: datetime | None

    def __post_init__(self) -> None:
        if not self.pickup.label.strip():
            raise ValueError("Pickup needs a label")

        if not (-90 <= self.pickup.lat <= 90 and -180 <= self.pickup.lng <= 180):
            raise ValueError("Pickup coordinates are out of range")

        if self.walk_seconds < 0:
            raise ValueError("Walk time cannot be negative")

        if self.rider_distance_meters < 0:
            raise ValueError("Rider distance cannot be negative")

        if self.detour_seconds is not None and self.detour_seconds < 0:
            raise ValueError("Detour time cannot be negative")

        if self.cost.amount_cents < 0:
            raise ValueError("Price cannot be negative")

        if self.cost.currency != "CAD":
            raise ValueError("Price must be in CAD")

        if not _is_aware(self.created_at):
            raise ValueError("Created time must include a timezone")

        if self.decided_at is not None:
            if not _is_aware(self.decided_at):
                raise ValueError("Decision time must include a timezone")
            if self.decided_at < self.created_at:
                raise ValueError("Decision time cannot be before creation time")

    @classmethod
    def create(
        cls,
        *,
        trip_id: UUID,
        rider_id: UUID,
        pickup: Location,
        walk_seconds: int,
        rider_distance_meters: int,
        detour_seconds: int | None,
        cost: Quote,
        now: datetime,
        auto_accepted: bool = False,
        request_id: UUID | None = None,
    ) -> "SeatRequest":
        return cls(
            id=request_id if request_id is not None else uuid4(),
            trip_id=trip_id,
            rider_id=rider_id,
            pickup=pickup,
            walk_seconds=walk_seconds,
            rider_distance_meters=rider_distance_meters,
            detour_seconds=detour_seconds,
            cost=cost,
            status=RequestStatus.PENDING,
            auto_accepted=auto_accepted,
            created_at=now,
            decided_at=None,
        )

    @property
    def holds_seat(self) -> bool:
        return self.status is RequestStatus.ACCEPTED

    def accept(self, now: datetime) -> "SeatRequest":
        if self.status is not RequestStatus.PENDING:
            raise RequestNotPendingError()
        return replace(self, status=RequestStatus.ACCEPTED, decided_at=now)

    def decline(self, now: datetime) -> "SeatRequest":
        if self.status not in (RequestStatus.PENDING, RequestStatus.ACCEPTED):
            raise RequestNotDecidableError()
        return replace(self, status=RequestStatus.DECLINED, decided_at=now)

    def cancel(self, now: datetime) -> "SeatRequest":
        if self.status not in (RequestStatus.PENDING, RequestStatus.ACCEPTED):
            raise RequestNotCancellableError()
        return replace(self, status=RequestStatus.CANCELLED, decided_at=now)
