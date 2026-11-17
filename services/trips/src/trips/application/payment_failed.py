"""Return a reserved seat once when Payments reports a definitive hold failure (#153)."""

from datetime import datetime
from uuid import UUID

from trips.application.ports import SeatRequestRepository
from trips.domain.request_errors import RequestNotFoundError
from trips.domain.seat_request import RequestStatus


class HandlePaymentFailed:
    def __init__(self, requests: SeatRequestRepository) -> None:
        self.requests = requests

    async def execute(
        self, *, request_id: UUID, trip_id: UUID, rider_id: UUID, now: datetime
    ) -> bool:
        request = await self.requests.get(request_id)
        if request is None:
            raise RequestNotFoundError()
        if request.trip_id != trip_id or request.rider_id != rider_id:
            raise ValueError("PaymentFailed identity does not match the saved request")
        # Same lock order as accept/decline/cancel. Reload after acquiring the trip lock
        # because another action may have returned the seat while this handler waited.
        await self.requests.lock_trip(trip_id)
        request = await self.requests.get(request_id)
        if request is None:
            raise RequestNotFoundError()
        if request.status is not RequestStatus.ACCEPTED:
            return False
        failed = request.fail_payment(now)
        if not await self.requests.save_decision(failed, expected=RequestStatus.ACCEPTED):
            return False
        await self.requests.release_seat(trip_id)
        await self.requests.renumber_accepted(trip_id)
        return True
