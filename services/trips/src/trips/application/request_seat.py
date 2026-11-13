"""Create a rider's seat request (#137)."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from trips.application.ports import (
    PricingService,
    RiderCardService,
    SeatRequestEvents,
    SeatRequestRepository,
    TripRepository,
)
from trips.application.request_routing import RequestRoutingService
from trips.domain.request_eligibility import RequestEligibility, ensure_request_eligible
from trips.domain.request_errors import TripNotFoundError
from trips.domain.seat_request import SeatRequest
from trips.domain.values import Point, TripMatch, ride_meters


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
    ) -> None:
        self.trips = trips
        self.requests = requests
        self.routing = routing
        self.pricing = pricing
        self.cards = cards
        self.events = events

    async def execute(self, command: RequestSeatCommand) -> SeatRequest:
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
        )

        accepted_pickups = await self.requests.list_accepted_pickups(command.trip_id)
        detour = await self.routing.estimate_detour(
            trip_id=command.trip_id,
            accepted_pickups=accepted_pickups,
            new_pickup=pickup.location,
        )

        rider_distance = ride_meters(
            trip.direction,
            trip.distance_meters,
            TripMatch(
                trip_id=trip.id,
                pickup=pickup.location,
                walk_seconds=pickup.walk_seconds,
                meters_to_trip_end=pickup.meters_to_trip_end,
            ),
        )
        quote = await self.pricing.quote(rider_distance)

        request = SeatRequest.create(
            trip_id=command.trip_id,
            rider_id=command.rider_id,
            pickup=pickup.location,
            walk_seconds=pickup.walk_seconds,
            rider_distance_meters=rider_distance,
            detour_seconds=detour.added_seconds,
            cost=quote,
            now=command.now,
        )

        await self.requests.add(request)
        await self.events.seat_requested(request, trip)
        return request
