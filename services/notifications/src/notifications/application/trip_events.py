"""What Notifications does for each request, trip, driver and payment event (#146): keep
``trip_members`` in step, and tell the right people."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from notifications.application.notify import Notify
from notifications.application.ports import TripMembers
from notifications.domain import messages
from notifications.domain.messages import PaymentFailureReason


class TripEventNotifications:
    def __init__(self, notify: Notify, members: TripMembers) -> None:
        self._notify = notify
        self._members = members

    async def seat_requested(
        self, *, request_id: UUID, trip_id: UUID, driver_id: UUID, departure_at: datetime
    ) -> None:
        await self._members.add_driver(trip_id, driver_id)
        await self._notify(
            [
                messages.seat_requested(
                    driver_id=driver_id,
                    trip_id=trip_id,
                    request_id=request_id,
                    departure_at=departure_at,
                )
            ]
        )

    async def request_accepted(
        self,
        *,
        request_id: UUID,
        trip_id: UUID,
        rider_id: UUID,
        driver_id: UUID,
        departure_at: datetime,
        pickup_label: str,
    ) -> None:
        await self._members.add_driver(trip_id, driver_id)
        await self._members.add_rider(trip_id, rider_id)
        await self._notify(
            [
                messages.request_accepted(
                    rider_id=rider_id,
                    trip_id=trip_id,
                    request_id=request_id,
                    departure_at=departure_at,
                    pickup_label=pickup_label,
                )
            ]
        )

    async def request_declined(
        self, *, request_id: UUID, trip_id: UUID, rider_id: UUID, was_accepted: bool
    ) -> None:
        await self._members.remove_rider(trip_id, rider_id)
        await self._notify(
            [
                messages.request_declined(
                    rider_id=rider_id,
                    trip_id=trip_id,
                    request_id=request_id,
                    was_accepted=was_accepted,
                )
            ]
        )

    async def request_cancelled(
        self,
        *,
        request_id: UUID,
        trip_id: UUID,
        rider_id: UUID,
        driver_id: UUID,
        was_accepted: bool,
    ) -> None:
        await self._members.remove_rider(trip_id, rider_id)
        await self._notify(
            [
                messages.request_cancelled(
                    driver_id=driver_id,
                    trip_id=trip_id,
                    request_id=request_id,
                    was_accepted=was_accepted,
                )
            ]
        )

    async def trip_cancelled(
        self, *, trip_id: UUID, rider_ids: Sequence[UUID], departure_at: datetime
    ) -> None:
        # Trips lists every rider with a pending or accepted request: they all need to know,
        # including those still waiting, who aren't trip members yet.
        await self._members.end_trip(trip_id)
        await self._notify(
            messages.trip_cancelled(rider_ids=rider_ids, trip_id=trip_id, departure_at=departure_at)
        )

    async def driver_approved(self, *, driver_id: UUID) -> None:
        await self._notify([messages.driver_approved(driver_id=driver_id)])

    async def driver_rejected(self, *, driver_id: UUID, reason: str) -> None:
        await self._notify([messages.driver_rejected(driver_id=driver_id, reason=reason)])

    async def payment_failed(
        self,
        *,
        request_id: UUID,
        trip_id: UUID,
        rider_id: UUID,
        reason: PaymentFailureReason,
    ) -> None:
        # Trips frees the seat when the hold fails, so the rider is no longer on the trip.
        await self._members.remove_rider(trip_id, rider_id)
        await self._notify(
            [
                messages.payment_failed(
                    rider_id=rider_id, trip_id=trip_id, request_id=request_id, reason=reason
                )
            ]
        )
