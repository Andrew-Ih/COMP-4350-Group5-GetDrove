"""HTTP adapter for OSRM, the routing engine (ADR 0008, infra/osrm/README.md).

OSRM's route service: https://project-osrm.org/docs/v5.24.0/api/#route-service
"""

from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from routing.application.ports import DrivingRoute
from routing.domain.errors import NoRouteError, RoutingEngineUnavailableError
from routing.domain.values import LatLng

# OSRM answers these (with HTTP 400) when the points are valid but can't be driven between:
# NoRoute when nothing connects them, NoSegment when a point can't be matched to a road.
NO_ROUTE_CODES = {"NoRoute", "NoSegment"}

# How far OSRM may move a point to reach a road. Without a limit it moves any point to the
# nearest road on the map, however far: a place in Toronto became the edge of Winnipeg.
# Beyond this, OSRM answers NoSegment.
MAX_SNAP_METERS = 500

# Routes are stored in PostgreSQL INTEGER columns.
MAX_INT = 2**31 - 1


class _Geometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[tuple[float, float]] = Field(min_length=2)  # [lng, lat] pairs


class _Route(BaseModel):
    distance: float = Field(ge=0, le=MAX_INT)  # meters
    duration: float = Field(ge=0, le=MAX_INT)  # seconds
    geometry: _Geometry


class _RouteResponse(BaseModel):
    code: str
    routes: list[_Route] = []


class OSRMRoutingEngine:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def driving_route(self, origin: LatLng, destination: LatLng) -> DrivingRoute:
        # OSRM takes coordinates as longitude,latitude.
        coordinates = f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"

        try:
            response = await self.client.get(
                f"/route/v1/driving/{coordinates}",
                params={
                    "overview": "full",
                    "geometries": "geojson",
                    "radiuses": f"{MAX_SNAP_METERS};{MAX_SNAP_METERS}",
                },
            )
            # OSRM's error responses are JSON too, with the reason in `code`.
            data = _RouteResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RoutingEngineUnavailableError() from exc

        if data.code in NO_ROUTE_CODES:
            raise NoRouteError()

        if response.status_code != 200 or data.code != "Ok" or not data.routes:
            raise RoutingEngineUnavailableError()

        route = data.routes[0]
        return DrivingRoute(
            path=tuple(LatLng(lat=lat, lng=lng) for lng, lat in route.geometry.coordinates),
            distance_meters=round(route.distance),
            duration_seconds=round(route.duration),
        )
