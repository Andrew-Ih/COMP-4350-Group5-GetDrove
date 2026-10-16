"""HTTP adapter for the Routing microservice."""

from uuid import UUID

import httpx

from trips.application.ports import RouteEstimate
from trips.domain.values import Location


class RoutingUnavailableError(Exception):
    """Routing could not compute a route."""


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
            response.raise_for_status()
            data = response.json()

            if data["tripId"] != str(trip_id):
                raise RoutingUnavailableError("Routing returned a different trip ID")

            return RouteEstimate(
                distance_meters=int(data["distanceMeters"]),
                duration_seconds=int(data["durationSeconds"]),
            )

        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RoutingUnavailableError("Failed to compute driving route") from exc
