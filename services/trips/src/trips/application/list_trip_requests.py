"""The driver's list of requests for one of their trips (#139)."""

import logging
from dataclasses import dataclass
from uuid import UUID

from trips.application.ports import (
    RiderProfile,
    RiderProfileService,
    SeatRequestRepository,
    TripRepository,
)
from trips.domain.request_errors import (
    NotTripDriverError,
    TripNotFoundError,
)
from trips.domain.seat_request import RequestStatus, SeatRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ListTripRequestsCommand:
    trip_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class DriverRequest:
    request: SeatRequest
    rider: RiderProfile
    pickup_order: int | None


class ListTripRequests:
    def __init__(
        self,
        *,
        trips: TripRepository,
        requests: SeatRequestRepository,
        riders: RiderProfileService,
    ) -> None:
        self.trips = trips
        self.requests = requests
        self.riders = riders

    async def execute(self, command: ListTripRequestsCommand) -> list[DriverRequest]:
        trip = await self.trips.get(command.trip_id)
        if trip is None:
            raise TripNotFoundError()
        if trip.driver_id != command.user_id:
            raise NotTripDriverError()

        open_requests = await self.requests.list_open_for_trip(trip.id)
        if not open_requests:
            return []

        profiles = await self.riders.get_many([request.rider_id for request in open_requests])

        items: list[DriverRequest] = []
        order = 0
        for request in open_requests:
            pickup_order = None
            if request.status is RequestStatus.ACCEPTED:
                order += 1
                pickup_order = order
            rider = profiles.get(request.rider_id)
            if rider is None:
                logger.warning(
                    "Skipping request %s: Accounts has no profile for its rider", request.id
                )
                continue
            items.append(DriverRequest(request, rider, pickup_order))
        return items
