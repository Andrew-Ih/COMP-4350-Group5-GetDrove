"""Tests for the OSRM HTTP adapter, with OSRM mocked."""

from collections.abc import Callable

import httpx
import pytest

from routing.adapters.osrm import OSRMRoutingEngine
from routing.application.ports import DrivingRoute
from routing.domain.errors import NoRouteError, RoutingEngineUnavailableError
from routing.domain.values import LatLng

type Handler = Callable[[httpx.Request], httpx.Response]

HOME = LatLng(lat=49.82, lng=-97.15)
CAMPUS = LatLng(lat=49.8075, lng=-97.1366)


async def driving_route(handler: Handler) -> DrivingRoute:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-car:5000"
    ) as client:
        return await OSRMRoutingEngine(client).driving_route(HOME, CAMPUS)


async def test_driving_route(osrm_route: Handler) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return osrm_route(request)

    route = await driving_route(handler)

    # OSRM takes longitude,latitude, and returns the full route as GeoJSON.
    [request] = requests
    assert request.method == "GET"
    assert request.url.path == "/route/v1/driving/-97.15,49.82;-97.1366,49.8075"
    assert request.url.params["overview"] == "full"
    assert request.url.params["geometries"] == "geojson"
    # Points far from any road (e.g. outside the Winnipeg map) are NoSegment, not moved.
    assert request.url.params["radiuses"] == "500;500"

    assert route.path == (HOME, LatLng(lat=49.815, lng=-97.14), CAMPUS)
    # OSRM's fractional meters and seconds are rounded to whole numbers.
    assert route.distance_meters == 6000
    assert route.duration_seconds == 900


async def test_no_route_is_invalid_input(osrm_no_route: Handler) -> None:
    with pytest.raises(NoRouteError):
        await driving_route(osrm_no_route)


async def test_engine_failure_is_unavailable(osrm_failure: Handler) -> None:
    with pytest.raises(RoutingEngineUnavailableError):
        await driving_route(osrm_failure)
