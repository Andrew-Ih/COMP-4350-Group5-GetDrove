"""Routing HTTP calls used when creating a seat request."""

from collections.abc import Sequence
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from trips.application.request_routing import DetourEstimate, SelectedPickup
from trips.domain.errors import RoutingUnavailableError
from trips.domain.request_errors import PickupNotAvailableError
from trips.domain.values import Location, Point


class _PickupPoint(BaseModel):
    id: str = Field(strict=True, min_length=1, max_length=64)
    label: str = Field(strict=True, min_length=1, max_length=200)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    walk_seconds: int = Field(alias="walkSeconds", strict=True, ge=0, le=2**31 - 1)
    meters_to_trip_end: int = Field(alias="riderDistanceMeters", strict=True, ge=0, le=2**31 - 1)


class _PickupPointsResponse(BaseModel):
    pickups: list[_PickupPoint] = Field(max_length=3)


class _DetourResponse(BaseModel):
    added_seconds: int = Field(alias="addedSeconds", strict=True, ge=0, le=2**31 - 1)
    position: int = Field(strict=True, ge=0)
    total_seconds: int = Field(alias="totalSeconds", strict=True, ge=0, le=2**31 - 1)


class HTTPRequestRoutingService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def select_pickup(
        self, *, trip_id: UUID, rider: Point, pickup_id: str, exclude: Sequence[str] = ()
    ) -> SelectedPickup:
        try:
            response = await self.client.post(
                "/internal/pickup-points",
                json={
                    "tripId": str(trip_id),
                    "rider": {"lat": rider.lat, "lng": rider.lng},
                    "limit": 3,
                    "exclude": list(exclude),
                },
            )
            response.raise_for_status()
            data = _PickupPointsResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RoutingUnavailableError(
                "Could not validate the pickup point. Please try again."
            ) from exc

        ids = [point.id for point in data.pickups]
        if len(ids) != len(set(ids)):
            raise RoutingUnavailableError("Routing returned duplicate pickup IDs.")

        for point in data.pickups:
            if point.id == pickup_id:
                return SelectedPickup(
                    id=point.id,
                    location=Location(
                        label=point.label,
                        lat=point.lat,
                        lng=point.lng,
                    ),
                    walk_seconds=point.walk_seconds,
                    meters_to_trip_end=point.meters_to_trip_end,
                )

        raise PickupNotAvailableError()

    async def estimate_detour(
        self,
        *,
        trip_id: UUID,
        accepted_pickups: Sequence[Location],
        new_pickup: Location,
    ) -> DetourEstimate:
        if len(accepted_pickups) > 6:
            raise ValueError("At most six accepted pickups can be sent to Routing.")

        try:
            response = await self.client.post(
                "/internal/detours",
                json={
                    "tripId": str(trip_id),
                    "acceptedPickups": [
                        {"lat": point.lat, "lng": point.lng} for point in accepted_pickups
                    ],
                    "newPickup": {"lat": new_pickup.lat, "lng": new_pickup.lng},
                },
            )
            response.raise_for_status()
            data = _DetourResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RoutingUnavailableError(
                "Could not calculate the pickup detour. Please try again."
            ) from exc

        if data.position > len(accepted_pickups):
            raise RoutingUnavailableError("Routing returned an invalid pickup position.")

        if data.total_seconds < data.added_seconds:
            raise RoutingUnavailableError("Routing returned inconsistent driving times.")

        return DetourEstimate(
            added_seconds=data.added_seconds,
            position=data.position,
            total_seconds=data.total_seconds,
        )
