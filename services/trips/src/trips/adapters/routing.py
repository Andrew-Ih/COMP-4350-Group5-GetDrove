"""HTTP adapter for the Routing microservice."""

from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from trips.application.ports import RouteEstimate
from trips.domain.errors import RoutingInvalidLocationError, RoutingUnavailableError
from trips.domain.values import Location


class _RouteResponse(BaseModel):
    trip_id: str = Field(alias="tripId", strict=True)
    # PostgreSQL stores these metrics as signed INTEGERs. Reject coercion (including
    # booleans and fractional numbers) and values that cannot be persisted.
    distance_meters: int = Field(alias="distanceMeters", strict=True, ge=0, le=2**31 - 1)
    duration_seconds: int = Field(alias="durationSeconds", strict=True, ge=0, le=2**31 - 1)


class HTTPRoutingService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def compute_route(
        self,
        trip_id: UUID,
        origin: Location,
        destination: Location,
    ) -> RouteEstimate:
        payload = {
            "tripId": str(trip_id),
            "origin": {
                "lat": origin.lat,
                "lng": origin.lng,
            },
            "destination": {
                "lat": destination.lat,
                "lng": destination.lng,
            },
        }

        try:
            response = await self.client.post(
                "/internal/routes",
                json=payload,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 422:
                    raise RoutingInvalidLocationError() from exc
                raise
            data = _RouteResponse.model_validate(response.json())

            if data.trip_id != str(trip_id):
                raise RoutingUnavailableError()

            return RouteEstimate(
                distance_meters=data.distance_meters,
                duration_seconds=data.duration_seconds,
            )

        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RoutingUnavailableError() from exc
