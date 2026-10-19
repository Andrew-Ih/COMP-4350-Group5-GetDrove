"""Fake OSRM responses shared by the adapter and API tests."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

type Handler = Callable[[httpx.Request], httpx.Response]

# A short drive from Pembina Highway to campus, as OSRM returns it ([lng, lat] pairs).
OSRM_PATH = [[-97.15, 49.82], [-97.14, 49.815], [-97.1366, 49.8075]]


def osrm_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 6000.4,
                    "duration": 899.6,
                    "geometry": {"type": "LineString", "coordinates": OSRM_PATH},
                }
            ],
        },
    )


@pytest.fixture
def osrm_route() -> Handler:
    """OSRM finds a route. Its fractional meters and seconds round to 6000 and 900."""
    return osrm_ok


@pytest.fixture(
    params=[
        "timeout",
        "connect-error",
        "http-500",
        "invalid-json",
        "html",
        "error-code",
        "no-routes",
        "ok-with-400",
        "missing-geometry",
        "one-point",
        "negative-distance",
        "overflow-duration",
    ]
)
def osrm_failure(request: pytest.FixtureRequest) -> Handler:
    """Every way OSRM can fail that means "try again later" (503), not "bad input" (422)."""
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("OSRM timed out", request=message)
        if case == "connect-error":
            raise httpx.ConnectError("OSRM is not running", request=message)
        if case == "http-500":
            return httpx.Response(500, json={"code": "Error", "message": "boom"})
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "html":
            return httpx.Response(502, content=b"<html>Bad gateway</html>")
        if case == "error-code":
            return httpx.Response(400, json={"code": "InvalidQuery", "message": "bad"})
        if case == "no-routes":
            return httpx.Response(200, json={"code": "Ok", "routes": []})
        if case == "ok-with-400":
            return httpx.Response(400, json=osrm_ok(message).json())

        route: dict[str, Any] = osrm_ok(message).json()["routes"][0]
        if case == "missing-geometry":
            del route["geometry"]
        elif case == "one-point":
            route["geometry"]["coordinates"] = OSRM_PATH[:1]
        elif case == "negative-distance":
            route["distance"] = -1
        elif case == "overflow-duration":
            route["duration"] = 2**31
        return httpx.Response(200, json={"code": "Ok", "routes": [route]})

    return handler


@pytest.fixture(params=["NoRoute", "NoSegment"])
def osrm_no_route(request: pytest.FixtureRequest) -> Handler:
    """OSRM can't drive between the points: the caller's input is the problem (422)."""

    def handler(message: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": request.param, "message": "Impossible route"})

    return handler
