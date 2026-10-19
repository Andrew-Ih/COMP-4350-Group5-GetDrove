"""HTTP adapters for OSRM, the routing engine (ADR 0008, infra/osrm/README.md).

Two instances: car (driving routes, road names) and foot (walking times).
OSRM's API: https://project-osrm.org/docs/v5.24.0/api/
"""

import asyncio
from collections.abc import Sequence
from itertools import batched
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from routing.application.ports import DrivingRoute
from routing.domain.errors import NoRouteError, RoutingEngineUnavailableError
from routing.domain.values import LatLng, Walk

# OSRM answers these (with HTTP 400) when the points are valid but can't be driven between:
# NoRoute when nothing connects them, NoSegment when a point can't be matched to a road.
NO_ROUTE_CODES = {"NoRoute", "NoSegment"}

# How far OSRM may move a point to reach a road. Without a limit it moves any point to the
# nearest road on the map, however far: a place in Toronto became the edge of Winnipeg.
# Beyond this, OSRM answers NoSegment.
MAX_SNAP_METERS = 500

# Routes are stored in PostgreSQL INTEGER columns.
MAX_INT = 2**31 - 1

# osrm-routed accepts at most 100 coordinates in a table request by default (--max-table-size),
# and one of them is the rider.
MAX_TABLE_DESTINATIONS = 99

# Candidate roads for a pickup label: the nearest are often unnamed service roads or parking
# lot aisles, so look a little further, but not so far that the name misleads the rider.
ROAD_NAME_CANDIDATES = 20
MAX_ROAD_NAME_METERS = 150


def _coordinate(point: LatLng) -> str:
    # OSRM takes coordinates as longitude,latitude.
    return f"{point.lng},{point.lat}"


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


class _Waypoint(BaseModel):
    name: str = ""
    distance: float = 0  # meters from the point asked about


class _NearestResponse(BaseModel):
    code: str
    waypoints: list[_Waypoint] = []


class _TableResponse(BaseModel):
    code: str
    # One row per source (just the rider); None where there's no route.
    durations: list[list[float | None]] = []
    distances: list[list[float | None]] = []


class OSRMRoutingEngine:
    """The car profile."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def road_name(self, point: LatLng) -> str | None:
        try:
            response = await self.client.get(
                f"/nearest/v1/driving/{_coordinate(point)}",
                params={"number": ROAD_NAME_CANDIDATES},
            )
            data = _NearestResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError):
            return None

        if response.status_code != 200 or data.code != "Ok":
            return None
        # Nearest first: the closest road that has a name, if it's close enough.
        return next(
            (
                waypoint.name
                for waypoint in data.waypoints
                if waypoint.name and waypoint.distance <= MAX_ROAD_NAME_METERS
            ),
            None,
        )

    async def driving_route(self, origin: LatLng, destination: LatLng) -> DrivingRoute:
        coordinates = f"{_coordinate(origin)};{_coordinate(destination)}"

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


class OSRMWalkingEngine:
    """The foot profile: walking times from a rider to many points, with OSRM's table service
    (https://project-osrm.org/docs/v5.24.0/api/#table-service)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def walks(self, origin: LatLng, destinations: Sequence[LatLng]) -> list[Walk | None]:
        # The chunks are independent, so ask for them all at once: search time stays about
        # one request however many trips match. gather keeps them in order. The last chunk
        # is shorter, so not strict.
        chunks = batched(destinations, MAX_TABLE_DESTINATIONS, strict=False)
        results = await asyncio.gather(*(self._walks(origin, chunk) for chunk in chunks))
        return [walk for chunk in results for walk in chunk]

    async def _walks(self, origin: LatLng, destinations: Sequence[LatLng]) -> list[Walk | None]:
        coordinates = ";".join(_coordinate(point) for point in (origin, *destinations))
        try:
            response = await self.client.get(
                f"/table/v1/foot/{coordinates}",
                params={"sources": "0", "annotations": "duration,distance"},
            )
            data = _TableResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise RoutingEngineUnavailableError() from exc

        # The rider's row: the rider to itself, then each destination in order.
        expected = len(destinations) + 1
        if (
            response.status_code != 200
            or data.code != "Ok"
            or len(data.durations) != 1
            or len(data.distances) != 1
            or len(data.durations[0]) != expected
            or len(data.distances[0]) != expected
        ):
            raise RoutingEngineUnavailableError()

        return [
            Walk(seconds=round(seconds), meters=round(meters))
            if seconds is not None and meters is not None
            else None
            for seconds, meters in zip(data.durations[0][1:], data.distances[0][1:], strict=True)
        ]
