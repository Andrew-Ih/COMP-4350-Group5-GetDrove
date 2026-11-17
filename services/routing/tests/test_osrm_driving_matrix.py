"""Tests for OSRM driving times between many points (table service), with OSRM mocked."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from routing.adapters.osrm import MAX_SNAP_METERS, OSRMRoutingEngine
from routing.domain.errors import RoutingEngineUnavailableError
from routing.domain.values import LatLng

type Handler = Callable[[httpx.Request], httpx.Response]

CLIENT_TIMEOUT = 2.5
DETOUR_TIMEOUT = 0.8


def points(count: int) -> list[LatLng]:
    return [LatLng(lat=49.8 + i / 10_000, lng=-97.1) for i in range(count)]


def table(request: httpx.Request) -> httpx.Response:
    """A table answer for however many points were asked: 100 seconds per step apart."""
    size = len(request.url.path.removeprefix("/table/v1/driving/").split(";"))
    rows = [[100.5 * abs(i - j) for j in range(size)] for i in range(size)]
    return httpx.Response(200, json={"code": "Ok", "durations": rows})


async def durations(
    handler: Handler, stops: list[LatLng], detour_timeout: float | None = DETOUR_TIMEOUT
) -> list[list[float]]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://osrm-car:5000",
        timeout=CLIENT_TIMEOUT,
    ) as client:
        engine = OSRMRoutingEngine(client, detour_timeout_seconds=detour_timeout)
        return await engine.durations(stops)


async def test_durations_asks_for_every_pair_in_the_points_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return table(request)

    result = await durations(handler, points(3))

    [request] = requests
    assert request.method == "GET"
    # Longitude,latitude, in the order given; no sources or destinations, so all pairs.
    assert request.url.path == "/table/v1/driving/-97.1,49.8;-97.1,49.8001;-97.1,49.8002"
    assert request.url.params["annotations"] == "duration"
    assert request.url.params["radiuses"] == ";".join([str(MAX_SNAP_METERS)] * 3)
    assert "sources" not in request.url.params
    # Not rounded: the detour is rounded once, at the end.
    assert result == [[0.0, 100.5, 201.0], [100.5, 0.0, 100.5], [201.0, 100.5, 0.0]]


async def test_durations_uses_the_detour_timeout_not_the_clients() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return table(request)

    await durations(handler, points(3))

    [request] = requests
    timeout = request.extensions["timeout"]
    assert timeout == {
        "connect": DETOUR_TIMEOUT,
        "read": DETOUR_TIMEOUT,
        "write": DETOUR_TIMEOUT,
        "pool": DETOUR_TIMEOUT,
    }
    assert DETOUR_TIMEOUT < CLIENT_TIMEOUT


async def test_durations_without_a_detour_timeout_uses_the_clients() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return table(request)

    await durations(handler, points(3), detour_timeout=None)

    [request] = requests
    assert request.extensions["timeout"]["read"] == CLIENT_TIMEOUT


async def test_durations_are_not_symmetric_when_one_way_streets_say_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "Ok", "durations": [[0, 60], [240, 0]]})

    assert await durations(handler, points(2)) == [[0, 60], [240, 0]]


async def test_durations_with_no_points_asks_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("OSRM must not be called without points")

    assert await durations(handler, []) == []


@pytest.fixture(
    params=[
        "timeout",
        "connect-error",
        "http-500",
        "invalid-json",
        "no-segment",
        "missing-durations",
        "short-row",
        "missing-row",
        "no-route-pair",
        "string-duration",
    ]
)
def table_failure(request: pytest.FixtureRequest) -> Handler:
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("OSRM timed out", request=message)
        if case == "connect-error":
            raise httpx.ConnectError("OSRM is not running", request=message)
        if case == "http-500":
            return httpx.Response(500, json={"code": "Error"})
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "no-segment":
            return httpx.Response(400, json={"code": "NoSegment", "message": "No road nearby"})
        body: dict[str, Any] = table(message).json()
        if case == "missing-durations":
            del body["durations"]
        elif case == "short-row":
            body["durations"][1].pop()
        elif case == "missing-row":
            body["durations"].pop()
        elif case == "no-route-pair":
            body["durations"][0][2] = None
        elif case == "string-duration":
            body["durations"][0][1] = "soon"
        return httpx.Response(200, json=body)

    return handler


async def test_driving_matrix_failure_is_unavailable(table_failure: Handler) -> None:
    with pytest.raises(RoutingEngineUnavailableError):
        await durations(table_failure, points(3))


def selected(request: httpx.Request) -> httpx.Response:
    """A table answer honouring ``sources`` and ``destinations``: point i to point j takes
    10 * i + j seconds, so a row and a column can't be mixed up."""
    size = len(request.url.path.removeprefix("/table/v1/driving/").split(";"))

    def indexes(name: str) -> list[int]:
        value = request.url.params.get(name)
        return list(range(size)) if value is None else [int(i) for i in value.split(";")]

    rows = [[float(10 * i + j) for j in indexes("destinations")] for i in indexes("sources")]
    return httpx.Response(200, json={"code": "Ok", "durations": rows})


async def test_durations_around_asks_for_the_row_and_the_column() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return selected(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-car:5000", timeout=2.5
    ) as client:
        engine = OSRMRoutingEngine(client, detour_timeout_seconds=DETOUR_TIMEOUT)
        result = await engine.durations_around(points(1)[0], points(3)[1:])

    # From the point to each other (0 -> 1, 0 -> 2), then from each other to the point.
    assert result == ([1.0, 2.0], [10.0, 20.0])
    asked = {(r.url.params["sources"], r.url.params["destinations"]) for r in requests}
    assert asked == {("0", "1;2"), ("1;2", "0")}
    assert all(r.extensions["timeout"]["read"] == DETOUR_TIMEOUT for r in requests)


async def test_durations_around_nothing_asks_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("OSRM must not be called without other points")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-car:5000"
    ) as client:
        assert await OSRMRoutingEngine(client).durations_around(points(1)[0], []) == ([], [])
