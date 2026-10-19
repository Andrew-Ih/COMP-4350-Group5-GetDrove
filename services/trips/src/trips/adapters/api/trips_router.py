"""Trips API (Sprint 1): post a trip, my trips, trip detail and search.

POST is implemented by issue #94 and search by #97. The other read handlers remain contract
stubs (#95). Paths here are relative to the gateway prefix /api/trips.
"""

from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime

from common_security.dependencies import AuthenticatedUser
from trips.adapters.api.dependencies import PostTripService, SearchTripsService
from trips.adapters.api.schemas import (
    Cost,
    Pickup,
    Place,
    PostTripRequest,
    Problem,
    SearchResult,
    Trip,
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

    return Trip(
        id=trip.id,
        driver_id=trip.driver_id,
        direction=trip.direction,
        origin=Place(
            label=trip.origin.label,
            lat=trip.origin.lat,
            lng=trip.origin.lng,
        ),
        destination=Place(
            label=trip.destination.label,
            lat=trip.destination.lat,
            lng=trip.destination.lng,
        ),
        departure_at=trip.departure_at,
        estimated_arrival_at=trip.estimated_arrival_at,
        duration_seconds=trip.duration_seconds,
        distance_meters=trip.distance_meters,
        seats_total=trip.seats_total,
        seats_available=trip.seats_available,
        status=trip.status,
    )


@router.get(
    "/mine",
    summary="My upcoming trips",
    description="The logged-in user's upcoming trips, soonest first. `role=driver` lists trips "
    "they've posted. `role=rider` (trips they've requested) arrives in Sprint 2.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def my_trips(
    user: AuthenticatedUser,
    service: UpcomingTripsService,
    role: Annotated[Literal["driver", "rider"], Query()] = "driver",
) -> list[Trip]:
    if role == "rider":
        _not_implemented()
    else:
        trips = await service.execute(driver_id=user.id)

        return [
            Trip(
                id=trip.id,
                driver_id=trip.driver_id,
                direction=trip.direction,
                origin=Place(
                    label=trip.origin.label,
                    lat=trip.origin.lat,
                    lng=trip.origin.lng,
                ),
                destination=Place(
                    label=trip.destination.label,
                    lat=trip.destination.lat,
                    lng=trip.destination.lng,
                ),
                departure_at=trip.departure_at,
                estimated_arrival_at=trip.estimated_arrival_at,
                duration_seconds=trip.duration_seconds,
                distance_meters=trip.distance_meters,
                seats_total=trip.seats_total,
                seats_available=trip.seats_available,
                status=trip.status,
            )
            for trip in trips
        ]


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


@router.get(
    "/{trip_id}",
    summary="Trip detail",
    description="One trip. The driver's own end of the trip is returned only to its driver. "
    "The pickup point and cost for a specific rider are added in Sprint 2.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        404: _problem("No trip with this ID", "trip_not_found"),
    },
)
async def get_trip(
    trip_id: UUID,
    user: AuthenticatedUser,
) -> Trip:
    _not_implemented()
