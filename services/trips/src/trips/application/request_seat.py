"""Create a rider's seat request (#137), accepting it straight away if it meets the driver's
auto-accept rules (#43)."""

import logging
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from trips.application.ports import (
    AutoAcceptRulesRepository,
    PricingService,
    RiderCardService,
    RiderProfileService,
    SeatRequestEvents,
    SeatRequestRepository,
    TripRepository,
)
from trips.application.request_routing import RequestRoutingService
from trips.domain.auto_accept import AutoAcceptRules, auto_accept_allows
from trips.domain.entities import Trip
from trips.domain.request_eligibility import RequestEligibility, ensure_request_eligible
from trips.domain.request_errors import AccountsUnavailableError, TripNotFoundError
from trips.domain.seat_request import SeatRequest
from trips.domain.values import Point, ride_meters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestSeatCommand:
    trip_id: UUID
    rider_id: UUID
    rider: Point
    pickup_id: str
    now: datetime
    exclude: tuple[str, ...] = ()


class RequestSeat:
    def __init__(
        self,
        *,
        trips: TripRepository,
        requests: SeatRequestRepository,
        routing: RequestRoutingService,
        pricing: PricingService,
        cards: RiderCardService,
        events: SeatRequestEvents,
        auto_accept: AutoAcceptRulesRepository,
        riders: RiderProfileService,
    ) -> None:
        self.trips = trips
        self.requests = requests
        self.routing = routing
        self.pricing = pricing
        self.cards = cards
        self.events = events
        self.auto_accept = auto_accept
        self.riders = riders

    async def execute(self, command: RequestSeatCommand) -> SeatRequest:
        # One request at a time per rider (#359): without it, two requests for overlapping
        # trips could both pass the overlap check before either is saved.
        await self.requests.lock_rider(command.rider_id)
        trip = await self.trips.get(command.trip_id)

        already_requested = False
        overlapping = False
        if trip is not None:
            existing = await self.requests.get_active_for_trip(command.trip_id, command.rider_id)
            already_requested = existing is not None
            overlapping = await self.requests.has_overlapping_active_request(
                command.rider_id, trip.departure_at, trip.estimated_arrival_at
            )

        facts = RequestEligibility(
            trip=trip,
            rider_id=command.rider_id,
            now=command.now,
            already_requested=already_requested,
            overlapping_request=overlapping,
            has_card=True,
        )
        ensure_request_eligible(facts)
        if trip is None:
            raise TripNotFoundError()

        has_card = await self.cards.has_card(command.rider_id)
        ensure_request_eligible(replace(facts, has_card=has_card))

        pickup = await self.routing.select_pickup(
            trip_id=command.trip_id,
            rider=command.rider,
            pickup_id=command.pickup_id,
            exclude=command.exclude,
        )

        accepted_pickups = await self.requests.list_accepted_pickups(command.trip_id)
        detour = await self.routing.estimate_detour(
            trip_id=command.trip_id,
            accepted_pickups=accepted_pickups,
            new_pickup=pickup.location,
        )

        # Priced like search and the trip detail (#30), so the cost matches what the rider saw.
        rider_distance = ride_meters(
            trip.direction, trip.distance_meters, pickup.meters_to_trip_end
        )
        quote = await self.pricing.quote(rider_distance)

        # Looked up before the trip is locked, so a slow Accounts never holds up other riders.
        rules = await self.auto_accept.get(trip.driver_id) or AutoAcceptRules()
        rating_known, rider_rating = await self._rider_rating(rules, command.rider_id)

        request = SeatRequest.create(
            trip_id=command.trip_id,
            rider_id=command.rider_id,
            pickup=pickup.location,
            walk_seconds=pickup.walk_seconds,
            rider_distance_meters=rider_distance,
            detour_seconds=detour.added_seconds,
            cost=quote,
            now=command.now,
            detour_position=detour.position,
        )

        # Cancellation locks the same trip row. Recheck after external calls, while holding
        # the lock through the request and outbox writes.
        await self.requests.lock_trip(trip.id)
        current_trip = await self.trips.get(trip.id)
        ensure_request_eligible(replace(facts, trip=current_trip, has_card=has_card))
        await self.requests.add(request)
        await self.events.seat_requested(request, trip)

        allowed = current_trip is not None and auto_accept_allows(
            rules,
            detour_seconds=request.detour_seconds,
            rating_known=rating_known,
            rider_rating=rider_rating,
            seats_available=current_trip.seats_available,
        )
        if allowed and current_trip is not None:
            return await self._auto_accept(request, current_trip, command.now)
        return request

    async def _rider_rating(
        self, rules: AutoAcceptRules, rider_id: UUID
    ) -> tuple[bool, float | None]:
        """(known, rating). Accounts is only asked when the rules have a minimum rating. If
        it can't answer, or doesn't know the rider, the rating is unknown and the request
        waits for the driver."""
        if not rules.enabled or rules.min_rating is None:
            return True, None
        try:
            profiles = await self.riders.get_many([rider_id])
        except AccountsUnavailableError:
            logger.warning("Accounts couldn't give a rider's rating; leaving the request pending")
            return False, None
        profile = profiles.get(rider_id)
        return (True, profile.rating) if profile is not None else (False, None)

    async def _auto_accept(self, request: SeatRequest, trip: Trip, now: datetime) -> SeatRequest:
        """Accepts like a driver would (#138): the same atomic seat update, so auto-accept
        never goes over the seat count. The seat is taken first: if none is left, nothing
        has changed and the request simply stays pending. The trip is still locked, so the
        pickups accepted so far haven't moved since the detour was worked out."""
        if not await self.requests.take_seat(trip.id):
            return request
        accepted = replace(request.accept(now), auto_accepted=True)
        await self.requests.save_decision(accepted, expected=request.status)
        order = await self.requests.place_accepted(accepted, position=request.detour_position)
        accepted = replace(accepted, pickup_order=order)
        await self.events.request_accepted(accepted, trip)
        return accepted
