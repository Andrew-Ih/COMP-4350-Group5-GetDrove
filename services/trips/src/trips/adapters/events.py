"""Trip events persisted with the Trip transaction."""

from datetime import datetime
from uuid import UUID

from events.catalog import (
    DriverLateCancellation,
    RequestAccepted,
    RequestCancelled,
    RequestDeclined,
    SeatRequested,
    TripCancelled,
    TripPosted,
)
from events.outbox import OutboxPublisher
from trips.domain.entities import Trip
from trips.domain.seat_request import SeatRequest


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

    async def request_accepted(self, request: SeatRequest, trip: Trip) -> None:
        await self.publisher.publish(
            RequestAccepted(
                request_id=request.id,
                trip_id=request.trip_id,
                rider_id=request.rider_id,
                driver_id=trip.driver_id,
                departure_at=trip.departure_at,
                pickup_label=request.pickup.label,
                # So consumers know whether the label is the pickup (to campus) or the
                # drop-off (leaving campus, picked up on campus) (#352, #354).
                direction=trip.direction.value,
                amount_cents=request.cost.amount_cents,
                currency=request.cost.currency,
                auto_accepted=request.auto_accepted,
            )
        )

    async def request_declined(
        self, request: SeatRequest, trip: Trip, *, was_accepted: bool
    ) -> None:
        await self.publisher.publish(
            RequestDeclined(
                request_id=request.id,
                trip_id=request.trip_id,
                rider_id=request.rider_id,
                driver_id=trip.driver_id,
                was_accepted=was_accepted,
            )
        )

    async def request_cancelled(
        self, request: SeatRequest, trip: Trip, *, was_accepted: bool
    ) -> None:
        await self.publisher.publish(
            RequestCancelled(
                request_id=request.id,
                trip_id=request.trip_id,
                rider_id=request.rider_id,
                driver_id=trip.driver_id,
                was_accepted=was_accepted,
            )
        )
