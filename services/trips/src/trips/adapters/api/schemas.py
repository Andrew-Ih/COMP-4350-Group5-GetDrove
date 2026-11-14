"""Request and response models for the Trips API: the contract the frontend and other
services build against (issues #108, #262).

JSON fields are camelCase; times are ISO 8601 with a timezone; money is in cents.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
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
    series_id: UUID | None = Field(
        default=None, description="The recurring series this trip belongs to, if any."
    )

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


# ---------------------------------------------------------------- recurring trips (#15)

Weekday = Literal["mon", "tue", "wed", "thu", "fri"]
WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri")
WINNIPEG = ZoneInfo("America/Winnipeg")


class PostTripSeriesRequest(PostTripRequest):
    weekdays: list[Weekday] = Field(
        min_length=1,
        max_length=5,
        description="The weekdays it repeats on. Each one at most once. The first "
        "departure must be on one of them (its Winnipeg day).",
        examples=[["mon", "wed", "fri"]],
    )
    end_date: date = Field(
        description="The last day a trip can be on (Winnipeg date). After the first "
        "departure and at most 16 weeks after it.",
        examples=["2026-12-11"],
    )

    @field_validator("weekdays")
    @classmethod
    def _each_weekday_once(cls, weekdays: list[Weekday]) -> list[Weekday]:
        if len(set(weekdays)) != len(weekdays):
            raise ValueError("Each weekday can only be listed once")
        return weekdays

    @field_validator("weekdays")
    @classmethod
    def _first_departure_on_a_weekday(
        cls, weekdays: list[Weekday], info: ValidationInfo
    ) -> list[Weekday]:
        departure_at = info.data.get("departure_at")
        if departure_at is None:  # already invalid; that error is reported instead
            return weekdays
        local_day = departure_at.astimezone(WINNIPEG).weekday()
        if local_day >= len(WEEKDAYS) or WEEKDAYS[local_day] not in weekdays:
            raise ValueError("The first departure must be on one of the chosen weekdays")
        return weekdays

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
                    "departureAt": "2026-11-16T13:10:00Z",
                    "seatsTotal": 3,
                    "weekdays": ["mon", "wed", "fri"],
                    "endDate": "2026-12-11",
                }
            ]
        }
    )


class TripSeriesResult(ApiModel):
    series_id: UUID
    trips: list[Trip] = Field(description="The trips created, one per matching day.")
    skipped_dates: list[date] = Field(
        description="Days left out because they clash with the driver's other trips."
    )


# ---------------------------------------------------------------- pickup options (#28)


class PickupOption(ApiModel):
    """A point on the driver's route where this rider could be picked up."""

    id: str = Field(
        description="Opaque ID from Routing. Send it back when requesting a seat.",
        examples=["s42"],
    )
    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float
    walk_seconds: int = Field(ge=0, description="Walking time from the rider to this point.")
    cost: Cost | None = Field(
        description="This rider's share if picked up here. Null if it can't be priced right now."
    )


# ---------------------------------------------------------------- seat requests (#34)


class RequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAYMENT_FAILED = "payment_failed"


class RequestPickup(ApiModel):
    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float
    walk_seconds: int = Field(ge=0)


class SeatRequest(ApiModel):
    """A rider's request for a seat, as the rider sees it."""

    id: UUID
    trip_id: UUID
    rider_id: UUID
    status: RequestStatus
    pickup: RequestPickup
    cost: Cost = Field(
        description="Saved when the request was made: this is what gets held and charged."
    )
    auto_accepted: bool
    created_at: AwareDatetime
    decided_at: AwareDatetime | None = Field(
        description="When it was accepted, declined, cancelled or expired."
    )


# How many rejected pickup points the trip detail and a seat request can be asked to leave
# out (#136); passed on to Routing, which has the same limit.
MAX_EXCLUDED_PICKUPS = 20

PickupPointId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class SeatRequestBody(ApiModel):
    lat: float = Field(
        ge=-90, le=90, description="The rider's location. Used to check the pickup, never stored."
    )
    lng: float = Field(ge=-180, le=180)
    pickup_id: str = Field(
        min_length=1, max_length=64, description="One of the trip detail's `pickups`."
    )
    exclude: list[PickupPointId] = Field(
        default_factory=list,
        max_length=MAX_EXCLUDED_PICKUPS,
        description="The same `exclude` the trip detail was loaded with (#136), so a pickup "
        "point that was only offered because the rider rejected others is still accepted "
        "(#299). Passed on to Routing, never stored.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"lat": 49.8722, "lng": -97.1561, "pickupId": "s42"},
                {"lat": 49.8722, "lng": -97.1561, "pickupId": "s50", "exclude": ["s42", "s45"]},
            ]
        }
    )


class RiderSummary(ApiModel):
    id: UUID
    first_name: str = Field(examples=["Priya"])
    rating: float | None = Field(
        ge=1, le=5, description="Average rating; null if they have no ratings yet."
    )
    rating_count: int = Field(ge=0)
    no_show_count: int = Field(ge=0)


class DriverPickup(ApiModel):
    label: str = Field(examples=["Osborne St & River Ave"])
    lat: float
    lng: float


class DriverRequestView(ApiModel):
    """A request on one of the driver's trips, with what they need to decide."""

    id: UUID
    status: RequestStatus
    rider: RiderSummary
    pickup: DriverPickup = Field(description="Only the pickup point, never where the rider is.")
    pickup_order: int | None = Field(
        ge=1, description="Place in the pickup order (1 = first). Accepted requests only."
    )
    detour_seconds: int | None = Field(
        ge=0,
        description="Extra driving time this pickup adds. Null if it couldn't be worked out: "
        "show an error state, not a number.",
    )
    cost: Cost
    auto_accepted: bool
    created_at: AwareDatetime
    decided_at: AwareDatetime | None


# ---------------------------------------------------------------- trip detail and my trips


class TripVehicle(ApiModel):
    make: str = Field(examples=["Honda"])
    model: str = Field(examples=["Civic"])
    colour: str = Field(examples=["Blue"])
    plate: str = Field(examples=["ABC123"])


class TripDetail(ApiModel):
    trip: Trip = Field(description="The driver's own end is null unless you're the driver.")
    vehicle: TripVehicle | None = Field(
        description="The driver's vehicle, with its plate, so an accepted rider can find their "
        "car. Only for the trip's driver and riders with an accepted request on it; null for "
        "everyone else (make, model and colour are on the driver's public profile)."
    )
    pickups: list[PickupOption] = Field(
        max_length=3,
        description="Up to 3 pickup points, best first. Empty if `lat`/`lng` weren't sent or "
        "the trip doesn't pass within walking distance of them.",
    )
    my_request: SeatRequest | None = Field(
        description="Your pending or accepted request on this trip, if you have one."
    )


class RiderTrip(ApiModel):
    trip: Trip = Field(description="The driver's end is null (private).")
    request: SeatRequest


# ---------------------------------------------------------------- auto-accept (#41)


class AutoAcceptRules(ApiModel):
    enabled: bool = Field(description="Applies to new requests only.")
    max_detour_minutes: int = Field(
        ge=0,
        le=30,
        description="Accept only if the pickup adds at most this much: a request's "
        "`detourSeconds` must be at most `maxDetourMinutes * 60`.",
        examples=[5],
    )
    min_rating: float | None = Field(
        ge=1,
        le=5,
        description="Accept only riders rated at least this. Null: any rating. Riders with no "
        "ratings yet always pass.",
        examples=[4.0],
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
