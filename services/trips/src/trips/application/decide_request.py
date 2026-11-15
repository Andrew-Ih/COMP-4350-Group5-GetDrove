"""Accept, decline or cancel a seat request (#138), or read one (#358)."""

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from trips.application.ports import SeatRequestEvents, SeatRequestRepository, TripRepository
from trips.application.request_routing import RequestRoutingService
from trips.domain.entities import Trip
from trips.domain.errors import RoutingUnavailableError
from trips.domain.request_errors import (
    NotTripDriverError,
    NotYourRequestError,
    RequestNotCancellableError,
    RequestNotDecidableError,
    RequestNotFoundError,
    RequestNotPendingError,
    RequestNotVisibleError,
    SeatTakenError,
)
from trips.domain.seat_request import RequestStatus, SeatRequest
from trips.domain.values import TripStatus

logger = logging.getLogger(__name__)


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


class GetSeatRequest:
    """``GET /requests/{id}`` (#358): one request, for the rider who made it or the trip's
    driver, whatever its status, so the rider's screen sees it accepted or declined. Anyone
    else gets 403; an unknown ID 404."""

    def __init__(self, *, trips: TripRepository, requests: SeatRequestRepository) -> None:
        self.trips = trips
        self.requests = requests

    async def execute(self, request_id: UUID, user_id: UUID) -> SeatRequest:
        request = await self.requests.get(request_id)
        if request is None:
            raise RequestNotFoundError()
        if request.rider_id == user_id:
            return request
        trip = await self.trips.get(request.trip_id)
        if trip is None:
            raise RequestNotFoundError()
        if trip.driver_id != user_id:
            raise RequestNotVisibleError()
        return request


class AcceptRequest(_RequestAction):
    """The driver accepts (#138). The pickup goes where Routing places it on the route as it
    is now, with the pickups accepted so far (#360), not where it was placed when the rider
    asked: others may have been accepted since. If Routing can't answer, the position from
    the request is used, so a slow Routing never stops a driver accepting."""

    def __init__(
        self,
        *,
        trips: TripRepository,
        requests: SeatRequestRepository,
        events: SeatRequestEvents,
        routing: RequestRoutingService,
    ) -> None:
        super().__init__(trips=trips, requests=requests, events=events)
        self.routing = routing

    async def execute(self, command: RequestActionCommand) -> SeatRequest:
        request, trip = await self._load(command.request_id)
        if trip.driver_id != command.user_id:
            raise NotTripDriverError()
        if _started(trip, command.now):
            raise RequestNotPendingError("This trip has already started or been cancelled.")
        if request.status is not RequestStatus.PENDING:
            raise RequestNotPendingError()  # before asking Routing for nothing

        # The trip stays locked until the end, so the accepted pickups Routing is given are
        # still the accepted pickups when this one is placed.
        await self.requests.lock_trip(trip.id)
        position = await self._position_now(request)

        accepted = request.accept(command.now)
        if not await self.requests.save_decision(accepted, expected=RequestStatus.PENDING):
            raise RequestNotPendingError()
        if not await self.requests.take_seat(trip.id):
            raise SeatTakenError()
        order = await self.requests.place_accepted(accepted, position=position)
        accepted = replace(accepted, pickup_order=order)

        await self.events.request_accepted(accepted, trip)
        return accepted

    async def _position_now(self, request: SeatRequest) -> int | None:
        accepted_pickups = await self.requests.list_accepted_pickups(request.trip_id)
        try:
            detour = await self.routing.estimate_detour(
                trip_id=request.trip_id,
                accepted_pickups=accepted_pickups,
                new_pickup=request.pickup,
            )
        except RoutingUnavailableError:
            logger.warning(
                "Routing couldn't place request %s when accepting; using its position from "
                "when it was requested",
                request.id,
            )
            return request.detour_position
        return detour.position


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
            await self.requests.renumber_accepted(trip.id)

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
            await self.requests.renumber_accepted(trip.id)

        await self.events.request_cancelled(cancelled, trip, was_accepted=was_accepted)
        return cancelled
