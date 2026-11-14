"""Accept, decline or cancel a seat request (#138)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trips.application.ports import SeatRequestEvents, SeatRequestRepository, TripRepository
from trips.domain.entities import Trip
from trips.domain.request_errors import (
    NotTripDriverError,
    NotYourRequestError,
    RequestNotCancellableError,
    RequestNotDecidableError,
    RequestNotFoundError,
    RequestNotPendingError,
    SeatTakenError,
)
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import TripStatus


@dataclass(frozen=True)
class RequestActionCommand:
    request_id: UUID
    user_id: UUID
    now: datetime


def _started(trip: Trip, now: datetime) -> bool:
    return trip.status is not TripStatus.SCHEDULED or now >= trip.departure_at


class _RequestAction:
    def __init__(
        self,
        *,
        trips: TripRepository,
        requests: SeatRequestRepository,
        events: SeatRequestEvents,
    ) -> None:
        self.trips = trips
        self.requests = requests
        self.events = events

    async def _load(self, request_id: UUID) -> tuple[SeatRequest, Trip]:
        request = await self.requests.get(request_id)
        if request is None:
            raise RequestNotFoundError()
        trip = await self.trips.get(request.trip_id)
        if trip is None:
            raise RequestNotFoundError()
        return request, trip


class AcceptRequest(_RequestAction):
    async def execute(self, command: RequestActionCommand) -> SeatRequest:
        request, trip = await self._load(command.request_id)
        if trip.driver_id != command.user_id:
            raise NotTripDriverError()
        if _started(trip, command.now):
            raise RequestNotPendingError("This trip has already started or been cancelled.")

        accepted = request.accept(command.now)
        if not await self.requests.save_decision(accepted, expected=RequestStatus.PENDING):
            raise RequestNotPendingError()
        if not await self.requests.take_seat(trip.id):
            raise SeatTakenError()

        await self.events.request_accepted(accepted, trip)
        return accepted


class DeclineRequest(_RequestAction):
    async def execute(self, command: RequestActionCommand) -> SeatRequest:
        request, trip = await self._load(command.request_id)
        if trip.driver_id != command.user_id:
            raise NotTripDriverError()
        if _started(trip, command.now):
            raise RequestNotDecidableError()

        was_accepted = request.holds_seat
        declined = request.decline(command.now)
        if not await self.requests.save_decision(declined, expected=request.status):
            raise RequestNotDecidableError()
        if was_accepted:
            await self.requests.release_seat(trip.id)

        await self.events.request_declined(declined, trip, was_accepted=was_accepted)
        return declined


class CancelRequest(_RequestAction):
    async def execute(self, command: RequestActionCommand) -> SeatRequest:
        request, trip = await self._load(command.request_id)
        if request.rider_id != command.user_id:
            raise NotYourRequestError()
        if _started(trip, command.now):
            raise RequestNotCancellableError()

        was_accepted = request.holds_seat
        cancelled = request.cancel(command.now)
        if not await self.requests.save_decision(cancelled, expected=request.status):
            raise RequestNotCancellableError()
        if was_accepted:
            await self.requests.release_seat(trip.id)

        await self.events.request_cancelled(cancelled, trip, was_accepted=was_accepted)
        return cancelled
