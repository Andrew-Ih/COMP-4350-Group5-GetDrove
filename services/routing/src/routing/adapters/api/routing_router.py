"""Routing API (Sprint 1 contract, issue #108).

- Internal endpoints (/internal/...) are called by Trips inside Docker, e.g.
  http://routing:8000/internal/routes. The gateway never exposes them.
- The geometry endpoint is public (/api/routing/trips/{tripId}/geometry), for the map.

Implemented by issues #24 (POST /internal/routes), #25 and #26 (POST /internal/matches) and
#123 (the geometry endpoint).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from common_security.dependencies import AuthenticatedUser
from routing.adapters.api.dependencies import (
    ComputeRouteService,
    GetRouteService,
    MatchRiderService,
)
from routing.adapters.api.schemas import (
    LineString,
    Match,
    MatchRequest,
    MatchResponse,
    Pickup,
    Problem,
    RouteFeature,
    RouteProperties,
    RouteRequest,
    RouteResponse,
)
from routing.domain.values import LatLng

internal_router = APIRouter(prefix="/internal", tags=["internal"])
public_router = APIRouter(tags=["routes"])

Responses = dict[int | str, dict[str, Any]]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}
ENGINE_DOWN: Responses = {
    503: _problem(
        "The routing engine (OSRM) is unavailable or too slow", "routing_engine_unavailable"
    )
}


@internal_router.post(
    "/routes",
    summary="Compute and store a trip's driving route",
    description="Called by Trips when a trip is posted. Computes the driving route, stores it "
    "for matching, and returns its distance and duration. Target: under 3 seconds. "
    "Calling it again for the same trip replaces the route.",
    responses={**INVALID, **ENGINE_DOWN},
)
async def compute_route(body: RouteRequest, service: ComputeRouteService) -> RouteResponse:
    route = await service.execute(
        trip_id=body.trip_id,
        origin=LatLng(lat=body.origin.lat, lng=body.origin.lng),
        destination=LatLng(lat=body.destination.lat, lng=body.destination.lng),
    )

    return RouteResponse(
        trip_id=route.trip_id,
        distance_meters=route.distance_meters,
        duration_seconds=route.duration_seconds,
    )


@internal_router.post(
    "/matches",
    summary="Find which trips pass near a rider",
    description="From the candidate trips, returns those whose route passes within walking "
    "distance of the rider along the road network (a rider across a river with no nearby "
    "crossing doesn't match), with the best pickup point for each. Trips that don't match "
    "are left out; an empty list is a normal result.",
    responses={**INVALID, **ENGINE_DOWN},
)
async def match_trips(body: MatchRequest, service: MatchRiderService) -> MatchResponse:
    matches = await service.execute(
        rider=LatLng(lat=body.rider.lat, lng=body.rider.lng),
        trip_ids=body.trip_ids,
    )

    return MatchResponse(
        matches=[
            Match(
                trip_id=match.trip_id,
                pickup=Pickup(label=match.pickup_label, lat=match.pickup.lat, lng=match.pickup.lng),
                walk_seconds=match.walk_seconds,
                rider_distance_meters=match.rider_distance_meters,
            )
            for match in matches
        ]
    )


@public_router.get(
    "/trips/{trip_id}/geometry",
    summary="A trip's route for the map",
    description="The route as a GeoJSON LineString. From Sprint 2, riders get the route "
    "starting at their pickup point so the driver's start stays private; in Sprint 1 the "
    "full route is returned.",
    responses={
        **INVALID,
        401: _problem("Missing or invalid access token", "unauthorized"),
        404: _problem("No route for this trip", "route_not_found"),
    },
)
async def route_geometry(
    trip_id: UUID, user: AuthenticatedUser, service: GetRouteService
) -> RouteFeature:
    route = await service.execute(trip_id)

    return RouteFeature(
        geometry=LineString(coordinates=[(point.lng, point.lat) for point in route.path]),
        properties=RouteProperties(
            trip_id=route.trip_id,
            distance_meters=route.distance_meters,
            duration_seconds=route.duration_seconds,
        ),
    )
