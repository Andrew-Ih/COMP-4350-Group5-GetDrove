"""Trips API (Sprint 1): post a trip, my trips, trip detail and search.

These routes are the contract (issue #108): paths, inputs, outputs and errors are final,
but the handlers return 501 Not Implemented until the real code lands (#94, #95, #97).
Paths here are relative to the gateway prefix /api/trips.
"""

from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import AwareDatetime

from common_security.dependencies import AuthenticatedUser
from trips.adapters.api.schemas import PostTripRequest, Problem, SearchResult, Trip
from trips.domain.values import Direction

router = APIRouter(tags=["trips"])


def _problem(description: str, example_code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{example_code}`)"}


# Typed to match FastAPI's `responses` parameter, so they can be combined with ** below.
Responses = dict[int | str, dict[str, Any]]

UNAUTHORIZED: Responses = {401: _problem("Missing or invalid access token", "unauthorized")}
INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#108).")


@router.post(
    "/",
    status_code=201,
    summary="Post a trip",
    description="A driver posts a one-off trip to or from campus. The driving route is "
    "computed when the trip is posted; if it can't be, nothing is saved.",
    responses={
        **UNAUTHORIZED,
        422: _problem(
            "Invalid input, including seats outside 1-6 or a departure in the past",
            "invalid_input / departure_in_past",
        ),
        503: _problem("The route couldn't be computed right now", "routing_unavailable"),
    },
)
async def post_trip(body: PostTripRequest, user: AuthenticatedUser) -> Trip:
    _not_implemented()


@router.get(
    "/mine",
    summary="My upcoming trips",
    description="The logged-in user's upcoming trips, soonest first. `role=driver` lists trips "
    "they've posted. `role=rider` (trips they've requested) arrives in Sprint 2.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def my_trips(
    user: AuthenticatedUser, role: Annotated[Literal["driver", "rider"], Query()] = "driver"
) -> list[Trip]:
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
        503: _problem("Matching is unavailable right now", "routing_unavailable"),
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
) -> list[SearchResult]:
    _not_implemented()


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
async def get_trip(trip_id: UUID, user: AuthenticatedUser) -> Trip:
    _not_implemented()
