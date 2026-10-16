"""Tests for the Routing HTTP adapter."""

from uuid import uuid4

import httpx
import pytest

from trips.adapters.routing import (
    HTTPRoutingService,
    RoutingUnavailableError,
)
from trips.domain.values import Location


async def test_compute_route() -> None:
    trip_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/routes"
        assert request.method == "POST"

        return httpx.Response(
            200,
            json={
                "tripId": str(trip_id),
                "distanceMeters": 6000,
                "durationSeconds": 900,
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
            origin=Location("Home", 49.82, -97.15),
            destination=Location("Campus", 49.8075, -97.1366),
        )

    assert result.distance_meters == 6000
    assert result.duration_seconds == 900


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
            )
