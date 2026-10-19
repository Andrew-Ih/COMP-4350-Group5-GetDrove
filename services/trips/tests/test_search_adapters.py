"""Tests for the HTTP calls search makes (#97): Routing's matches and Payments' quotes."""

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from trips.adapters.payments import HTTPPricingService
from trips.adapters.routing import MAX_MATCH_TRIPS, HTTPRoutingService
from trips.domain.errors import PricingUnavailableError, RoutingUnavailableError
from trips.domain.values import Location, Point, Quote, TripMatch

type Handler = Callable[[httpx.Request], httpx.Response]

RIDER = Point(lat=49.85, lng=-97.15)


def matching(*matched: UUID) -> Handler:
    """Routing's answer: the given trips match, if they were asked about."""

    def handler(request: httpx.Request) -> httpx.Response:
        asked = set(json.loads(request.content)["tripIds"])
        return httpx.Response(
            200,
            json={
                "matches": [
                    {
                        "tripId": str(trip_id),
                        "pickup": {"label": "Pembina Highway", "lat": 49.84, "lng": -97.15},
                        "walkSeconds": 240,
                        "riderDistanceMeters": 4000,
                    }
                    for trip_id in matched
                    if str(trip_id) in asked
                ]
            },
        )

    return handler


async def match(handler: Handler, trip_ids: list[UUID]) -> list[TripMatch]:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        return await HTTPRoutingService(client).match(RIDER, trip_ids)


async def quote(handler: Handler, distance: int = 4000) -> Quote:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://payments:8000"
    ) as client:
        return await HTTPPricingService(client).quote(distance)


# ---------------------------------------------------------------- Routing: matches


async def test_match_sends_the_rider_and_candidates() -> None:
    hit, miss = uuid4(), uuid4()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return matching(hit)(request)

    result = await match(handler, [hit, miss])

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/internal/matches"
    assert json.loads(request.content) == {
        "rider": {"lat": 49.85, "lng": -97.15},
        "tripIds": [str(hit), str(miss)],
    }
    assert result == [
        TripMatch(
            trip_id=hit,
            pickup=Location("Pembina Highway", 49.84, -97.15),
            walk_seconds=240,
            meters_to_trip_end=4000,
        )
    ]


async def test_match_splits_large_requests() -> None:
    """Routing takes at most 500 candidates per request."""
    trip_ids = [uuid4() for _ in range(MAX_MATCH_TRIPS + 3)]
    sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sizes.append(len(json.loads(request.content)["tripIds"]))
        return matching(trip_ids[0], trip_ids[-1])(request)

    result = await match(handler, trip_ids)

    assert sizes == [MAX_MATCH_TRIPS, 3]
    assert [m.trip_id for m in result] == [trip_ids[0], trip_ids[-1]]


@pytest.fixture(
    params=[
        "timeout",
        "connect-error",
        "http-503",
        "http-422",
        "invalid-json",
        "missing-matches",
        "unknown-trip",
        "negative-walk",
        "float-distance",
        "string-walk",
        "bad-latitude",
    ]
)
def match_failure(request: pytest.FixtureRequest) -> Handler:
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("Routing timed out", request=message)
        if case == "connect-error":
            raise httpx.ConnectError("Routing is down", request=message)
        if case == "http-503":
            return httpx.Response(503, json={"code": "routing_engine_unavailable"})
        if case == "http-422":
            return httpx.Response(422, json={"code": "invalid_input"})
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "missing-matches":
            return httpx.Response(200, json={})
        asked = json.loads(message.content)["tripIds"][0]
        body: dict[str, Any] = {
            "tripId": asked,
            "pickup": {"label": "Pembina Highway", "lat": 49.84, "lng": -97.15},
            "walkSeconds": 240,
            "riderDistanceMeters": 4000,
        }
        if case == "unknown-trip":
            body["tripId"] = str(uuid4())
        elif case == "negative-walk":
            body["walkSeconds"] = -1
        elif case == "float-distance":
            body["riderDistanceMeters"] = 4000.5
        elif case == "string-walk":
            body["walkSeconds"] = "240"
        elif case == "bad-latitude":
            body["pickup"]["lat"] = 120
        return httpx.Response(200, json={"matches": [body]})

    return handler


async def test_match_failure_is_routing_unavailable(match_failure: Handler) -> None:
    with pytest.raises(RoutingUnavailableError) as error:
        await match(match_failure, [uuid4()])

    assert error.value.code == "routing_unavailable"
    assert "Matching is unavailable" in str(error.value)


# ---------------------------------------------------------------- Payments: quotes


async def test_quote_asks_for_the_riders_distance() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"amountCents": 180, "currency": "CAD", "explanation": "4.0 km at $0.45/km"},
        )

    result = await quote(handler, distance=4000)

    [request] = requests
    assert request.method == "POST"
    assert request.url.path == "/internal/quotes"
    assert json.loads(request.content) == {"distanceMeters": 4000}
    assert result == Quote(180, "CAD", "4.0 km at $0.45/km")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(501, json={"code": "not_implemented"}),  # until #99 lands
        httpx.Response(503, json={"code": "service_unavailable"}),
        httpx.Response(422, json={"code": "invalid_input"}),
        httpx.Response(200, content=b"not JSON"),
        httpx.Response(200, json={"amountCents": -5, "currency": "CAD", "explanation": "x"}),
        httpx.Response(200, json={"amountCents": 180, "currency": "USD", "explanation": "x"}),
        httpx.Response(200, json={"amountCents": "180", "currency": "CAD", "explanation": "x"}),
        httpx.Response(200, json={"amountCents": 180, "currency": "CAD"}),
    ],
)
async def test_quote_failure_is_pricing_unavailable(response: httpx.Response) -> None:
    with pytest.raises(PricingUnavailableError):
        await quote(lambda request: response)


async def test_quote_timeout_is_pricing_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Payments timed out", request=request)

    with pytest.raises(PricingUnavailableError):
        await quote(handler)
