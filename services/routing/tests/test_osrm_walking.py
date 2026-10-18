"""Tests for OSRM walking times (table service) and road names (nearest), with OSRM mocked."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from routing.adapters.osrm import (
    MAX_TABLE_DESTINATIONS,
    OSRMRoutingEngine,
    OSRMWalkingEngine,
)
from routing.domain.errors import RoutingEngineUnavailableError
from routing.domain.values import LatLng, Walk

type Handler = Callable[[httpx.Request], httpx.Response]

RIDER = LatLng(lat=49.85, lng=-97.15)


def points(count: int) -> list[LatLng]:
    return [LatLng(lat=49.8 + i / 10_000, lng=-97.1) for i in range(count)]


def table(request: httpx.Request) -> httpx.Response:
    """A table answer for however many points were asked: point i is 100 * i seconds away."""
    coordinates = request.url.path.removeprefix("/table/v1/foot/").split(";")
    row = [0.0] + [100.4 * i for i in range(1, len(coordinates))]
    return httpx.Response(
        200, json={"code": "Ok", "durations": [row], "distances": [[d * 1.39 for d in row]]}
    )


async def walks(handler: Handler, destinations: list[LatLng]) -> list[Walk | None]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-foot:5000"
    ) as client:
        return await OSRMWalkingEngine(client).walks(RIDER, destinations)


async def road_name(handler: Handler) -> str | None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://osrm-car:5000"
    ) as client:
        return await OSRMRoutingEngine(client).road_name(RIDER)


# ---------------------------------------------------------------- walking times


async def test_walks_asks_for_one_row_from_the_rider() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return table(request)

    result = await walks(handler, points(2))

    [request] = requests
    assert request.method == "GET"
    # The rider first, then each destination; longitude,latitude.
    assert request.url.path == "/table/v1/foot/-97.15,49.85;-97.1,49.8;-97.1,49.8001"
    assert request.url.params["sources"] == "0"
    assert request.url.params["annotations"] == "duration,distance"
    # Rounded to whole seconds and meters, in the destinations' order.
    assert result == [Walk(seconds=100, meters=140), Walk(seconds=201, meters=279)]


async def test_walks_splits_large_requests_and_keeps_the_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return table(request)

    count = MAX_TABLE_DESTINATIONS * 2 + 3
    result = await walks(handler, points(count))

    sizes = [len(r.url.path.split(";")) - 1 for r in requests]
    assert sizes == [MAX_TABLE_DESTINATIONS, MAX_TABLE_DESTINATIONS, 3]
    assert len(result) == count
    # The fake numbers each request's points from 1, so a new chunk starts again at 100 s.
    first_of_each_chunk = result[0], result[MAX_TABLE_DESTINATIONS], result[-3]
    assert first_of_each_chunk == (Walk(seconds=100, meters=140),) * 3
    assert result[MAX_TABLE_DESTINATIONS - 1] == Walk(seconds=9940, meters=13816)


async def test_walks_with_no_destinations_asks_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("OSRM must not be called without destinations")

    assert await walks(handler, []) == []


async def test_unreachable_destinations_are_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": "Ok", "durations": [[0, None, 300]], "distances": [[0, None, 400]]},
        )

    assert await walks(handler, points(2)) == [None, Walk(seconds=300, meters=400)]


@pytest.fixture(
    params=[
        "timeout",
        "connect-error",
        "http-500",
        "invalid-json",
        "error-code",
        "missing-durations",
        "short-row",
        "two-rows",
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
        if case == "error-code":
            return httpx.Response(400, json={"code": "TooBig", "message": "Too many points"})
        body: dict[str, Any] = table(message).json()
        if case == "missing-durations":
            del body["durations"]
        elif case == "short-row":
            body["durations"][0].pop()
        elif case == "two-rows":
            body["durations"].append(body["durations"][0])
        elif case == "string-duration":
            body["durations"][0][1] = "soon"
        return httpx.Response(200, json=body)

    return handler


async def test_walking_engine_failure_is_unavailable(table_failure: Handler) -> None:
    with pytest.raises(RoutingEngineUnavailableError):
        await walks(table_failure, points(2))


# ---------------------------------------------------------------- road names


def nearest(*roads: tuple[str, float]) -> Handler:
    """OSRM's nearest roads, nearest first, as (name, meters away)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/nearest/v1/driving/-97.15,49.85"
        assert request.url.params["number"] == "20"
        waypoints = [{"name": name, "distance": meters} for name, meters in roads]
        return httpx.Response(200, json={"code": "Ok", "waypoints": waypoints})

    return handler


async def test_road_name_is_the_nearest_named_road() -> None:
    roads = nearest(("", 0), ("Pembina Highway", 30), ("Chancellor Drive", 60))

    assert await road_name(roads) == "Pembina Highway"


async def test_road_name_looks_past_unnamed_service_roads() -> None:
    """A trip starting in a parking lot: the nearest named road is a few aisles away."""
    unnamed = [("", meters) for meters in (0, 21, 35, 35, 55, 60, 70)]

    assert await road_name(nearest(*unnamed, ("Allegheny Drive", 82))) == "Allegheny Drive"


@pytest.mark.parametrize("meters,name", [(150, "Allegheny Drive"), (151, None)])
async def test_road_name_must_be_close_enough_to_describe_the_pickup(
    meters: float, name: str | None
) -> None:
    assert await road_name(nearest(("", 0), ("Allegheny Drive", meters))) == name


async def test_road_name_is_none_when_no_road_has_a_name() -> None:
    assert await road_name(nearest(("", 0), ("", 40))) is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"code": "Error"}),
        httpx.Response(400, json={"code": "NoSegment"}),
        httpx.Response(200, content=b"not JSON"),
    ],
)
async def test_road_name_failure_is_none_not_an_error(response: httpx.Response) -> None:
    """A label is cosmetic: it must never fail a rider's search."""
    assert await road_name(lambda request: response) is None


async def test_road_name_timeout_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("OSRM timed out", request=request)

    assert await road_name(handler) is None
