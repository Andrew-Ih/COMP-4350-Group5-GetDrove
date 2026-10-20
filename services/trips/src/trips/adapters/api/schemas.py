"""Request and response models for the Trips API: the contract the frontend and other
services build against (issue #108).

JSON fields are camelCase; times are ISO 8601 with a timezone; money is in cents.
"""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from trips.domain.values import Direction, TripStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


class Place(ApiModel):
    """A named point. Labels come from the frontend's address search."""

    label: str = Field(min_length=1, max_length=200, examples=["Wolseley Ave & Arlington St"])
    lat: float = Field(ge=-90, le=90, examples=[49.8794])
    lng: float = Field(ge=-180, le=180, examples=[-97.1663])


# ---------------------------------------------------------------- post a trip


class PostTripRequest(ApiModel):
    direction: Direction = Field(
        description="to_campus: the driver starts at `place` and ends at campus. "
        "from_campus: the driver starts at campus and ends at `place`."
    )
    place: Place = Field(
        description="The driver's end of the trip (usually near home). Never shown to riders."
    )
    departure_at: AwareDatetime = Field(
        description="When the driver leaves. Must be in the future.",
        examples=["2026-10-20T13:10:00Z"],
    )
    seats_total: int = Field(ge=1, le=6, description="Seats offered to riders.", examples=[3])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "direction": "to_campus",
                    "place": {
                        "label": "Wolseley Ave & Arlington St",
                        "lat": 49.8794,
                        "lng": -97.1663,
                    },
                    "departureAt": "2026-10-20T13:10:00Z",
                    "seatsTotal": 3,
                }
            ]
        }
    )


# ---------------------------------------------------------------- a trip


class Trip(ApiModel):
    id: UUID
    driver_id: UUID
    direction: Direction
    origin: Place | None = Field(
        description="Where the trip starts. The driver's own end (their `place`) is only "
        "returned to the trip's driver; for everyone else it's null."
    )
    destination: Place | None = Field(
        description="Where the trip ends. Same privacy rule as `origin`."
    )
    departure_at: AwareDatetime
    estimated_arrival_at: AwareDatetime
    duration_seconds: int = Field(ge=0, description="Driving time from the computed route.")
    distance_meters: int = Field(ge=0, description="Driving distance from the computed route.")
    seats_total: int = Field(ge=1, le=6)
    seats_available: int = Field(ge=0, le=6)
    status: TripStatus

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11",
                    "driverId": "0c8d6a1e-7b44-4f0e-8f61-6a2a9d3c5e77",
                    "direction": "to_campus",
                    "origin": {
                        "label": "Wolseley Ave & Arlington St",
                        "lat": 49.8794,
                        "lng": -97.1663,
                    },
                    "destination": {
                        "label": "University of Manitoba, Fort Garry campus",
                        "lat": 49.8075,
                        "lng": -97.1366,
                    },
                    "departureAt": "2026-10-20T13:10:00Z",
                    "estimatedArrivalAt": "2026-10-20T13:32:00Z",
                    "durationSeconds": 1320,
                    "distanceMeters": 9800,
                    "seatsTotal": 3,
                    "seatsAvailable": 3,
                    "status": "scheduled",
                }
            ]
        }
    )


# ---------------------------------------------------------------- search


class Pickup(ApiModel):
    """Where the rider would be picked up, on the driver's route."""

    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float
    walk_seconds: int = Field(ge=0, description="Walking time from the rider to this point.")


class Cost(ApiModel):
    amount_cents: int = Field(ge=0, examples=[420])
    currency: Literal["CAD"] = "CAD"
    explanation: str = Field(
        description="One line explaining the amount.", examples=["9.3 km at $0.45/km"]
    )


class SearchResult(ApiModel):
    trip: Trip = Field(description="The driver's end of the trip is null (private).")
    pickup: Pickup
    cost: Cost | None = Field(
        description="The rider's estimated share. Null if the price can't be computed right "
        "now; the trip is still shown."
    )


# ---------------------------------------------------------------- errors (documentation)


class InvalidFieldOut(ApiModel):
    field: str = Field(examples=["seatsTotal"])
    message: str = Field(examples=["Input should be less than or equal to 6"])


class Problem(ApiModel):
    """Every error response (RFC 9457 Problem Details, `application/problem+json`)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str = Field(description="Stable error name for the frontend to check.")
    request_id: str | None = None
    errors: list[InvalidFieldOut] | None = Field(
        default=None, description="Only on 422: the fields that were invalid."
    )
