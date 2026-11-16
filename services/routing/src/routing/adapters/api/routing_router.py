"""Routing API (contracts: Sprint 1 #108, Sprint 2 #262).

- Internal endpoints (/internal/...) are called by Trips inside Docker, e.g.
  http://routing:8000/internal/routes. The gateway never exposes them.
- The geometry endpoint is public (/api/routing/trips/{tripId}/geometry), for the map.

Implemented by issues #24 (POST /internal/routes), #25 and #26 (POST /internal/matches),
#123 (the geometry endpoint), #29 (POST /internal/pickup-points) and #135 (the geometry hides
the driver's end from riders). Detours (#36, #38) return 501 until implemented.
"""

from typing import Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException

from common_security.dependencies import AuthenticatedUser
from routing.adapters.api.dependencies import (
    ComputeRouteService,
    GetRouteService,
    MatchRiderService,
    SuggestPickupsService,
)
from routing.adapters.api.schemas import (
    DetourRequest,
    DetourResponse,
    LineString,
    Match,
    MatchRequest,
    MatchResponse,
    Pickup,
    PickupPoint,
    PickupPointsRequest,
    PickupPointsResponse,
    Problem,
    RouteFeature,
    RouteProperties,
    RouteRequest,
    RouteResponse,
)
from routing.domain.values import Direction, LatLng

internal_router = APIRouter(prefix="/internal", tags=["internal"])
public_router = APIRouter(tags=["routes"])

Responses = dict[int | str, dict[str, Any]]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}
ROUTE_NOT_FOUND: Responses = {404: _problem("No route stored for this trip", "route_not_found")}
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
        driver_id=body.driver_id,
        direction=Direction(body.direction) if body.direction else None,
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


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#262).")


@internal_router.post(
    "/pickup-points",
    summary="Pickup points for a rider on a trip",
    description="Called by Trips for the trip detail and when a seat is requested. Returns "
    "up to `limit` points on the trip's route, shortest walk first, each on a road a car can "
    "stop on and away from both ends of the route. Points in `exclude` (ones the rider "
    "rejected) are never returned.",
    responses={**INVALID, **ROUTE_NOT_FOUND, **ENGINE_DOWN},
)
async def pickup_points(
    body: PickupPointsRequest, service: SuggestPickupsService
) -> PickupPointsResponse:
    pickups = await service.execute(
        trip_id=body.trip_id,
        rider=LatLng(lat=body.rider.lat, lng=body.rider.lng),
        limit=body.limit,
        exclude=body.exclude,
    )

    return PickupPointsResponse(
        pickups=[
            PickupPoint(
                id=pickup.id,
                label=pickup.label,
                lat=pickup.point.lat,
                lng=pickup.point.lng,
                walk_seconds=pickup.walk_seconds,
                rider_distance_meters=pickup.rider_distance_meters,
            )
            for pickup in pickups
        ]
    )


@internal_router.post(
    "/detours",
    summary="Extra driving time for a new pickup",
    description="Called by Trips when a seat is requested. Puts the new pickup at the best "
    "place among the accepted ones (cheapest insertion) and returns the time it adds. "
    "Target: under 1 second; when the routing engine is slow it fails fast with 503 rather "
    "than returning a wrong number.",
    responses={**INVALID, **ROUTE_NOT_FOUND, **ENGINE_DOWN},
)
async def detour(body: DetourRequest) -> DetourResponse:
    _not_implemented()


@public_router.get(
    "/trips/{trip_id}/geometry",
    summary="A trip's route for the map",
    description="The route as a GeoJSON LineString. The trip's driver gets the full route. "
    "Anyone else gets it with the driver's end cut off, by the same margin pickup points "
    "keep from the ends (300 m in a straight line), so the driver's home is never shown. "
    "Routes stored before Sprint 2 have no driver or direction: both ends are cut off for "
    "everyone (#135).",
    responses={
        **INVALID,
        401: _problem("Missing or invalid access token", "unauthorized"),
        404: _problem("No route for this trip", "route_not_found"),
    },
)
async def route_geometry(
    trip_id: UUID, user: AuthenticatedUser, service: GetRouteService
) -> RouteFeature:
    # The driver sees the whole route; anyone else, without the driver's own end (#135).
    route = await service.execute(trip_id, viewer_id=user.id)

    return RouteFeature(
        geometry=LineString(coordinates=[(point.lng, point.lat) for point in route.path]),
        properties=RouteProperties(
            trip_id=route.trip_id,
            distance_meters=route.distance_meters,
            duration_seconds=route.duration_seconds,
        ),
    )
