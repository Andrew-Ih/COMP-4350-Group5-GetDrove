"""HTTP adapter for the Routing microservice."""

from collections.abc import Sequence
from itertools import batched
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from trips.application.ports import RouteEstimate
from trips.domain.errors import RoutingInvalidLocationError, RoutingUnavailableError
from trips.domain.values import Location, Point, TripMatch

# Routing accepts at most this many candidate trips per match request (its contract).
MAX_MATCH_TRIPS = 500

MATCHING_UNAVAILABLE = "Matching is unavailable right now. Please try again."


class _Pickup(BaseModel):
    label: str = Field(strict=True)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class _Match(BaseModel):
    trip_id: UUID = Field(alias="tripId")
    pickup: _Pickup
    walk_seconds: int = Field(alias="walkSeconds", strict=True, ge=0)
    # Routing's name; it's the rest of the route from the pickup, whatever the direction.
    meters_to_trip_end: int = Field(alias="riderDistanceMeters", strict=True, ge=0)


class _MatchResponse(BaseModel):
    matches: list[_Match]


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

    async def match(self, rider: Point, trip_ids: Sequence[UUID]) -> list[TripMatch]:
        matches: list[TripMatch] = []
        # The last chunk is shorter, so not strict.
        for chunk in batched(trip_ids, MAX_MATCH_TRIPS, strict=False):
            matches.extend(await self._match(rider, chunk))
        return matches

    async def _match(self, rider: Point, trip_ids: Sequence[UUID]) -> list[TripMatch]:
        payload = {
            "rider": {"lat": rider.lat, "lng": rider.lng},
            "tripIds": [str(trip_id) for trip_id in trip_ids],
        }
        try:
            response = await self.client.post("/internal/matches", json=payload)
            response.raise_for_status()
            data = _MatchResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RoutingUnavailableError(MATCHING_UNAVAILABLE) from exc

        # Routing may only answer about the trips it was asked about.
        if any(match.trip_id not in trip_ids for match in data.matches):
            raise RoutingUnavailableError(MATCHING_UNAVAILABLE)

        return [
            TripMatch(
                trip_id=match.trip_id,
                pickup=Location(match.pickup.label, match.pickup.lat, match.pickup.lng),
                walk_seconds=match.walk_seconds,
                meters_to_trip_end=match.meters_to_trip_end,
            )
            for match in data.matches
        ]
