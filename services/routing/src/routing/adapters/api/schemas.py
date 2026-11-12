"""Request and response models for the Routing API (contracts: #108, #262)."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


class Point(ApiModel):
    lat: float = Field(ge=-90, le=90, examples=[49.8794])
    lng: float = Field(ge=-180, le=180, examples=[-97.1663])


# ---------------------------------------------------------------- compute a route


class RouteRequest(ApiModel):
    trip_id: UUID
    origin: Point
    destination: Point
    driver_id: UUID | None = Field(
        default=None,
        description="The trip's driver, who sees the full route on the map. Sent from Sprint "
        "2 (#135); null for routes stored before.",
    )
    direction: Literal["to_campus", "from_campus"] | None = Field(
        default=None,
        description="Which end is the driver's (the origin going to campus, the destination "
        "leaving it), so it can be hidden from riders. Null for routes stored before Sprint "
        "2: both ends are then hidden from everyone.",
    )


class RouteResponse(ApiModel):
    trip_id: UUID
    distance_meters: int = Field(ge=0, examples=[9800])
    duration_seconds: int = Field(ge=0, examples=[1320])


# ---------------------------------------------------------------- match a rider to trips


class MatchRequest(ApiModel):
    rider: Point = Field(description="The rider's location. Used for matching only, never stored.")
    trip_ids: list[UUID] = Field(
        max_length=500,
        description="Candidate trips Trips has already filtered by time, seats and status.",
    )


class Pickup(ApiModel):
    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float


class Match(ApiModel):
    trip_id: UUID
    pickup: Pickup = Field(
        description="Best point on the route for this rider: where they're picked up going to "
        "campus, or dropped off leaving it. Never near either end of the route, so the "
        "driver's own end stays private."
    )
    walk_seconds: int = Field(ge=0, description="Walking time from the rider to the pickup.")
    rider_distance_meters: int = Field(
        ge=0,
        description="Distance along the route from `pickup` to the trip's end. Going to "
        "campus, that's how far the rider rides; leaving campus, they ride the rest: the "
        "trip's distance minus this.",
    )


class MatchResponse(ApiModel):
    matches: list[Match] = Field(
        description="Only trips whose route passes within walking distance."
    )


# ---------------------------------------------------------------- pickup points (#29, #30)


# A pickup point's opaque ID (see PickupPoint.id), and how many a request can exclude.
PickupPointId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
MAX_EXCLUDED_PICKUPS = 20


class PickupPointsRequest(ApiModel):
    trip_id: UUID
    rider: Point = Field(
        description="The rider's location. Used for this answer only, never stored."
    )
    limit: int = Field(default=3, ge=1, le=5, description="How many points to return at most.")
    exclude: list[PickupPointId] = Field(
        default_factory=list,
        max_length=MAX_EXCLUDED_PICKUPS,
        description="IDs of points the rider rejected (#136). They're never returned, so the "
        "next best come back instead. At most 20.",
        examples=[["s42", "s45"]],
    )


class PickupPoint(ApiModel):
    id: str = Field(
        description="Opaque ID of this point on the stored route. Trips sends it back when "
        "the rider requests a seat.",
        examples=["s42"],
    )
    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float
    walk_seconds: int = Field(ge=0, description="Walking time from the rider to this point.")
    rider_distance_meters: int = Field(
        ge=0,
        description="Distance along the route from this point to the trip's end (as in "
        "`Match.riderDistanceMeters`).",
    )


class PickupPointsResponse(ApiModel):
    pickups: list[PickupPoint] = Field(
        description="Best (shortest walk) first. Never on an excluded road and never near "
        "either end of the route. Empty if the route doesn't pass within walking distance."
    )


# ---------------------------------------------------------------- detours (#36, #38)


class DetourRequest(ApiModel):
    trip_id: UUID
    accepted_pickups: list[Point] = Field(
        max_length=6, description="Pickups of the riders already accepted, in pickup order."
    )
    new_pickup: Point


class DetourResponse(ApiModel):
    added_seconds: int = Field(
        ge=0,
        description="Extra driving time for the new pickup, at its best place.",
        examples=[180],
    )
    position: int = Field(
        ge=0,
        description="Where the new pickup goes in the pickup order (0 = first).",
        examples=[1],
    )
    total_seconds: int = Field(
        ge=0, description="Driving time of the whole trip with the new pickup.", examples=[1500]
    )


# ---------------------------------------------------------------- geometry for the map


class LineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(description="[lng, lat] pairs (GeoJSON order).")


class RouteProperties(ApiModel):
    trip_id: UUID
    distance_meters: int
    duration_seconds: int


class RouteFeature(BaseModel):
    """A GeoJSON Feature (RFC 7946), ready for MapLibre."""

    type: Literal["Feature"] = "Feature"
    geometry: LineString
    properties: RouteProperties


# ---------------------------------------------------------------- errors (documentation)


class InvalidFieldOut(ApiModel):
    field: str
    message: str


class Problem(ApiModel):
    """Every error response (RFC 9457 Problem Details, `application/problem+json`)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str = Field(description="Stable error name.")
    request_id: str | None = None
    errors: list[InvalidFieldOut] | None = None
