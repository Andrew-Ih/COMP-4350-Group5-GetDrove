"""Request and response models for the Routing API (Sprint 1 contract, issue #108)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
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
    pickup: Pickup = Field(description="Best point on the route for this rider.")
    walk_seconds: int = Field(ge=0, description="Walking time from the rider to the pickup.")
    rider_distance_meters: int = Field(
        ge=0,
        description="Distance the rider travels in the car (from the pickup to the trip's end).",
    )


class MatchResponse(ApiModel):
    matches: list[Match] = Field(
        description="Only trips whose route passes within walking distance."
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
