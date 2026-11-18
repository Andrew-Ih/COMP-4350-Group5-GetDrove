"""Tests for the Routing HTTP adapter."""

import json
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest

from trips.adapters.routing import (
    HTTPRoutingService,
    RoutingUnavailableError,
)
from trips.domain.values import Direction, Location


@pytest.mark.parametrize("distance,duration", [(6000, 900), (0, 0)])
async def test_compute_route(distance: int, duration: int) -> None:
    trip_id = uuid4()

    driver_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/routes"
        assert request.method == "POST"
        # The driver and direction, so Routing hides the driver's end from riders (#135).
        body = json.loads(request.content)
        assert body["driverId"] == str(driver_id)
        assert body["direction"] == "from_campus"

        return httpx.Response(
            200,
            json={
                "tripId": str(trip_id),
                "distanceMeters": distance,
                "durationSeconds": duration,
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://routing:8000",
    ) as client:
        adapter = HTTPRoutingService(client)

        result = await adapter.compute_route(
            trip_id=trip_id,
            origin=Location("Campus", 49.8075, -97.1366),
            destination=Location("Home", 49.82, -97.15),
            driver_id=driver_id,
            direction=Direction.FROM_CAMPUS,
        )

    assert result.distance_meters == distance
    assert result.duration_seconds == duration


async def test_routing_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://routing:8000",
    ) as client:
        adapter = HTTPRoutingService(client)

        with pytest.raises(RoutingUnavailableError):
            await adapter.compute_route(
                trip_id=uuid4(),
                origin=Location("Home", 49.82, -97.15),
                destination=Location("Campus", 49.8075, -97.1366),
                driver_id=uuid4(),
                direction=Direction.TO_CAMPUS,
            )


async def test_invalid_routing_response(
    routing_failure: Callable[[httpx.Request], httpx.Response],
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(routing_failure), base_url="http://routing:8000"
    ) as client:
        with pytest.raises(RoutingUnavailableError):
            await HTTPRoutingService(client).compute_route(
                trip_id=uuid4(),
                origin=Location("Home", 49.82, -97.15),
                destination=Location("Campus", 49.8075, -97.1366),
                driver_id=uuid4(),
                direction=Direction.TO_CAMPUS,
            )
