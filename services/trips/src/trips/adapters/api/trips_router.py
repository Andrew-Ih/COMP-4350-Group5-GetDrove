"""Trips API: post a trip, my trips and search (Sprint 1), and the Sprint 2 contract (#262):
recurring trips, cancelling, trip detail with pickup points, seat requests, and auto-accept.

Endpoints that return 501 are contracts: their task implements them.
Paths here are relative to the gateway prefix /api/trips. Fixed paths (/mine, /search,
/series, /requests/..., /auto-accept) are declared before /{trip_id}, so they aren't read as
a trip ID.
"""

from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime

from common_security.dependencies import AuthenticatedUser
from common_web import InvalidField, InvalidInputError
from trips.adapters.api.dependencies import (
    PostTripService,
    SearchTripsService,
    UpcomingTripsService,
)
from trips.adapters.api.schemas import (
    MAX_EXCLUDED_PICKUPS,
    AutoAcceptRules,
    Cost,
    DriverRequestView,
    Pickup,
    PickupPointId,
    Place,
    PostTripRequest,
    PostTripSeriesRequest,
    Problem,
    RiderTrip,
    SearchResult,
    SeatRequest,
    SeatRequestBody,
    Trip,
    TripDetail,
    TripSeriesResult,
)
from trips.domain.entities import Trip as TripEntity
from trips.domain.values import Direction, Location, Point

router = APIRouter(tags=["trips"])


def _problem(description: str, example_code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{example_code}`)"}


# Typed to match FastAPI's `responses` parameter, so they can be combined with ** below.
Responses = dict[int | str, dict[str, Any]]

UNAUTHORIZED: Responses = {401: _problem("Missing or invalid access token", "unauthorized")}

INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}

TRIP_NOT_FOUND: Responses = {404: _problem("No trip with this ID", "trip_not_found")}

REQUEST_NOT_FOUND: Responses = {404: _problem("No request with this ID", "request_not_found")}

NOT_APPROVED: Responses = {
    403: _problem("Only approved drivers can post trips", "driver_not_approved")
}

When = Annotated[
    Literal["upcoming", "past"],
    Query(description="Upcoming (soonest first) or past (most recent first)."),
]


def _not_implemented() -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail="Not implemented yet: this is a contract (#108).",
    )


@router.post(
    "/",
    status_code=201,
    summary="Post a trip",
    description="A driver posts a one-off trip to or from campus. The driving route is "
    "computed when the trip is posted; if it can't be, nothing is saved.",
    responses={
        **UNAUTHORIZED,
        **NOT_APPROVED,
        422: _problem(
            "Invalid input, including seats outside 1-6, an unroutable place, "
            "or a departure in the past",
            "invalid_input / departure_in_past",
        ),
        503: _problem(
            "The route couldn't be computed right now",
            "routing_unavailable",
        ),
    },
)
async def post_trip(
    body: PostTripRequest,
    user: AuthenticatedUser,
    service: PostTripService,
) -> Trip:
    trip = await service.execute(
        driver_id=user.id,
        direction=body.direction,
        place=Location(
            label=body.place.label,
            lat=body.place.lat,
            lng=body.place.lng,
        ),
        departure_at=body.departure_at,
        seats_total=body.seats_total,
    )

    return _to_response(trip)


@router.post(
    "/series",
    status_code=201,
    summary="Post a recurring weekday trip",
    description="Creates one trip per matching weekday from the first departure up to "
    "`endDate`, all at the same Winnipeg time. Each is its own trip that riders request "
    "separately. Days that clash with the driver's other trips are skipped and listed in "
    "`skippedDates`.",
    responses={
        **UNAUTHORIZED,
        **NOT_APPROVED,
        422: _problem(
            "Invalid input, including a weekday listed twice, an end date before the first "
            "departure or more than 16 weeks after it, or a departure in the past",
            "invalid_input / departure_in_past",
        ),
        503: _problem("The route couldn't be computed right now", "routing_unavailable"),
    },
)
async def post_trip_series(
    body: PostTripSeriesRequest,
    user: AuthenticatedUser,
) -> TripSeriesResult:
    _not_implemented()


@router.get(
    "/mine",
    summary="My trips as a driver",
    description="Trips the logged-in user has posted, including cancelled ones. A rider's "
    "trips are at `GET /requests/mine`.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def my_trips(
    user: AuthenticatedUser,
    service: UpcomingTripsService,
    role: Annotated[
        Literal["driver"], Query(description="Kept for older clients; always `driver`.")
    ] = "driver",
    when: When = "upcoming",
) -> list[Trip]:
    if when == "past":
        _not_implemented()

    trips = await service.execute(driver_id=user.id)
    return [_to_response(trip) for trip in trips]


@router.get(
    "/requests/mine",
    summary="My trips as a rider",
    description="Trips the logged-in user has requested a seat on, each with their request "
    "and its status (pending, accepted, declined, cancelled, expired, payment failed). "
    "Cancelled trips are included, not removed.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def my_requests(user: AuthenticatedUser, when: When = "upcoming") -> list[RiderTrip]:
    _not_implemented()


@router.get(
    "/auto-accept",
    summary="My auto-accept rules",
    description="The driver's rules. If they've never set any: off, 5 minutes, no minimum rating.",
    responses=UNAUTHORIZED,
)
async def get_auto_accept(user: AuthenticatedUser) -> AutoAcceptRules:
    _not_implemented()


@router.put(
    "/auto-accept",
    summary="Set my auto-accept rules",
    description="A request is accepted automatically when auto-accept is on, its pickup adds "
    "at most `maxDetourMinutes` (`detourSeconds <= maxDetourMinutes * 60`), the rider is "
    "rated at least `minRating` (riders with no "
    "ratings yet pass), and a seat is free. Otherwise it waits for the driver. Changes apply "
    "to new requests only.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def put_auto_accept(body: AutoAcceptRules, user: AuthenticatedUser) -> AutoAcceptRules:
    _not_implemented()


@router.get(
    "/search",
    summary="Find trips that pass near the rider",
    description="Scheduled trips with free seats whose driving route passes within walking "
    "distance of the rider, excluding the rider's own trips, soonest first. For "
    "`to_campus`, `time` is when the rider wants to arrive (trips arriving in the hour "
    "before it); for `from_campus`, when they want to leave (trips leaving in the hour "
    "after it). An empty list is a normal result. The rider's location is used for "
    "matching only and is never stored or shown to drivers.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        503: _problem(
            "Matching is unavailable right now",
            "routing_unavailable",
        ),
    },
)
async def search_trips(
    user: AuthenticatedUser,
    lat: Annotated[float, Query(ge=-90, le=90, description="Rider's latitude.")],
    lng: Annotated[float, Query(ge=-180, le=180, description="Rider's longitude.")],
    direction: Annotated[Direction, Query()],
    time: Annotated[
        AwareDatetime,
        Query(description="Arrive by (to_campus) or leave after (from_campus)."),
    ],
    service: SearchTripsService,
) -> list[SearchResult]:
    results = await service.execute(
        rider_id=user.id, rider=Point(lat=lat, lng=lng), direction=direction, time=time
    )

    return [
        SearchResult(
            trip=_for_rider(result.trip),
            pickup=Pickup(
                label=result.match.pickup.label,
                lat=result.match.pickup.lat,
                lng=result.match.pickup.lng,
                walk_seconds=result.match.walk_seconds,
            ),
            cost=Cost(
                amount_cents=result.cost.amount_cents,
                explanation=result.cost.explanation,
            )
            if result.cost
            else None,
        )
        for result in results
    ]


@router.get(
    "/requests/{request_id}",
    summary="One seat request",
    description="For the rider who made it or the trip's driver, e.g. to see whether a "
    "pending request was accepted.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Not your request or your trip", "forbidden"),
        **REQUEST_NOT_FOUND,
    },
)
async def get_request(request_id: UUID, user: AuthenticatedUser) -> SeatRequest:
    _not_implemented()


@router.post(
    "/requests/{request_id}/accept",
    summary="Accept a request",
    description="The trip's driver gives the rider a seat. Taking the seat is atomic: when "
    "two requests race for the last seat, exactly one wins and the other gets `seat_taken`.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the trip's driver can accept", "not_trip_driver"),
        **REQUEST_NOT_FOUND,
        409: _problem(
            "No seat left, or the request isn't pending",
            "seat_taken / request_not_pending",
        ),
    },
)
async def accept_request(request_id: UUID, user: AuthenticatedUser) -> SeatRequest:
    _not_implemented()


@router.post(
    "/requests/{request_id}/decline",
    summary="Decline a request",
    description="The trip's driver turns down a pending request, or removes an accepted "
    "rider before the trip starts. An accepted rider's seat is freed straight away.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the trip's driver can decline", "not_trip_driver"),
        **REQUEST_NOT_FOUND,
        409: _problem(
            "Only pending or accepted requests on a trip that hasn't started can be declined",
            "request_not_decidable",
        ),
    },
)
async def decline_request(request_id: UUID, user: AuthenticatedUser) -> SeatRequest:
    _not_implemented()


@router.post(
    "/requests/{request_id}/cancel",
    summary="Cancel my request",
    description="The rider withdraws a pending or accepted request before the trip starts. "
    "An accepted seat is freed straight away and any hold on their card is released.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the rider who made it can cancel it", "not_your_request"),
        **REQUEST_NOT_FOUND,
        409: _problem(
            "Only pending or accepted requests on a trip that hasn't started can be cancelled",
            "request_not_cancellable",
        ),
    },
)
async def cancel_request(request_id: UUID, user: AuthenticatedUser) -> SeatRequest:
    _not_implemented()


@router.post(
    "/series/{series_id}/cancel",
    summary="Cancel a recurring series",
    description="Cancels every trip in the series that hasn't started. Riders are notified "
    "and holds released, as for a single cancellation. Returns the trips cancelled.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the series' driver can cancel it", "not_trip_driver"),
        404: _problem("No series with this ID", "series_not_found"),
    },
)
async def cancel_series(series_id: UUID, user: AuthenticatedUser) -> list[Trip]:
    _not_implemented()


def _place(location: Location) -> Place:
    return Place(label=location.label, lat=location.lat, lng=location.lng)


def _for_rider(trip: TripEntity) -> Trip:
    """A trip as someone other than its driver sees it: the driver's own end (near their
    home) is null. Only the campus end is shown."""
    to_campus = trip.direction == Direction.TO_CAMPUS
    return Trip(
        id=trip.id,
        driver_id=trip.driver_id,
        direction=trip.direction,
        origin=None if to_campus else _place(trip.origin),
        destination=_place(trip.destination) if to_campus else None,
        departure_at=trip.departure_at,
        estimated_arrival_at=trip.estimated_arrival_at,
        duration_seconds=trip.duration_seconds,
        distance_meters=trip.distance_meters,
        seats_total=trip.seats_total,
        seats_available=trip.seats_available,
        status=trip.status,
    )


def _to_response(trip: TripEntity) -> Trip:
    return Trip(
        id=trip.id,
        driver_id=trip.driver_id,
        direction=trip.direction,
        origin=_place(trip.origin),
        destination=_place(trip.destination),
        departure_at=trip.departure_at,
        estimated_arrival_at=trip.estimated_arrival_at,
        duration_seconds=trip.duration_seconds,
        distance_meters=trip.distance_meters,
        seats_total=trip.seats_total,
        seats_available=trip.seats_available,
        status=trip.status,
    )


@router.get(
    "/{trip_id}",
    summary="Trip detail",
    description="One trip, with up to 3 pickup points for the rider at `lat`/`lng` (each "
    "with its walking time and price) and the caller's own request on it, if any. The "
    "driver's own end of the trip is returned only to its driver. Send `lat` and `lng` "
    "together or not at all; they're used to find pickup points and never stored. "
    "`exclude` leaves out pickup points the rider rejected (#136), so the next best come "
    "back instead; it's ignored without `lat` and `lng`.",
    responses={
        **UNAUTHORIZED,
        422: _problem("Invalid input, including only one of `lat` and `lng`", "invalid_input"),
        **TRIP_NOT_FOUND,
        503: _problem("Pickup points can't be worked out right now", "routing_unavailable"),
    },
)
async def get_trip(
    trip_id: UUID,
    user: AuthenticatedUser,
    lat: Annotated[float | None, Query(ge=-90, le=90, description="Rider's latitude.")] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180, description="Rider's longitude.")] = None,
    exclude: Annotated[
        list[PickupPointId] | None,
        Query(
            max_length=MAX_EXCLUDED_PICKUPS,
            description="IDs of pickup points the rider rejected, repeated: "
            "`?exclude=s42&exclude=s45`. At most 20.",
        ),
    ] = None,
) -> TripDetail:
    if (lat is None) != (lng is None):
        missing = "lng" if lng is None else "lat"
        raise InvalidInputError(
            "Send lat and lng together.",
            errors=[InvalidField(field=missing, message="Send lat and lng together")],
        )
    _not_implemented()


@router.post(
    "/{trip_id}/cancel",
    summary="Cancel a trip",
    description="The driver cancels a trip that hasn't started. It disappears from search "
    "but stays in My trips as cancelled; riders are notified and holds released. "
    "Cancelling less than an hour before departure is recorded as a late cancellation.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the trip's driver can cancel it", "not_trip_driver"),
        **TRIP_NOT_FOUND,
        409: _problem(
            "The trip has already started, finished or been cancelled", "trip_not_cancellable"
        ),
    },
)
async def cancel_trip(trip_id: UUID, user: AuthenticatedUser) -> Trip:
    _not_implemented()


@router.post(
    "/{trip_id}/requests",
    status_code=201,
    summary="Request a seat",
    description="The rider asks for a seat, picked up at one of the trip detail's pickup "
    "points. The price is saved with the request and is what gets charged. The request is "
    "`pending` until the driver decides, or `accepted` straight away if it meets the "
    "driver's auto-accept rules. The rider needs a saved card first. Send the same "
    "`exclude` the trip detail was loaded with, so a point offered after the rider rejected "
    "others is still accepted.",
    responses={
        **UNAUTHORIZED,
        403: _problem("You can't request a seat on your own trip", "own_trip"),
        **TRIP_NOT_FOUND,
        409: _problem(
            "Already on this trip, another request overlaps in time, no seats left, the trip "
            "isn't open for requests, or no saved card",
            "already_requested / overlapping_request / trip_full / trip_not_open / card_required",
        ),
        422: _problem(
            "Invalid input, or the pickup point isn't available from where you are",
            "invalid_input / pickup_not_available",
        ),
        503: _problem("The pickup or detour can't be worked out right now", "routing_unavailable"),
    },
)
async def request_seat(
    trip_id: UUID, body: SeatRequestBody, user: AuthenticatedUser
) -> SeatRequest:
    _not_implemented()


@router.get(
    "/{trip_id}/requests",
    summary="Requests on my trip",
    description="For the trip's driver: pending requests first, then accepted ones, each "
    "with the rider's rating and no-shows, their pickup point and the detour it adds.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        403: _problem("Only the trip's driver can see its requests", "not_trip_driver"),
        **TRIP_NOT_FOUND,
    },
)
async def trip_requests(trip_id: UUID, user: AuthenticatedUser) -> list[DriverRequestView]:
    _not_implemented()
