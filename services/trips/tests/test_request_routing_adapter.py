"""Pickup and detour adapters against Routing's HTTP contract."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest

from trips.adapters.request_routing import HTTPRequestRoutingService
from trips.domain.errors import RoutingUnavailableError
from trips.domain.request_errors import PickupNotAvailableError
from trips.domain.values import Location, Point


def pickup_payload() -> dict[str, Any]:
    return {
        "id": "s42",
        "label": "Pembina pickup",
        "lat": 49.82,
        "lng": -97.15,
        "walkSeconds": 120,
        "riderDistanceMeters": 4000,
    }


async def test_selected_pickup_is_validated_and_returned() -> None:
    trip_id = uuid4()
    rider = Point(lat=49.821, lng=-97.151)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/internal/pickup-points"
        assert json.loads(request.content) == {
            "tripId": str(trip_id),
            "rider": {"lat": rider.lat, "lng": rider.lng},
            "limit": 3,
        }
        return httpx.Response(200, json={"pickups": [pickup_payload()]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        result = await HTTPRequestRoutingService(client).select_pickup(
            trip_id=trip_id, rider=rider, pickup_id="s42"
        )

    assert result.id == "s42"
    assert result.location == Location("Pembina pickup", 49.82, -97.15)
    assert result.walk_seconds == 120
    assert result.meters_to_trip_end == 4000


@pytest.mark.parametrize("empty", [True, False])
async def test_unavailable_pickup_id_is_rejected(empty: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"pickups": [] if empty else [pickup_payload()]},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        with pytest.raises(PickupNotAvailableError) as error:
            await HTTPRequestRoutingService(client).select_pickup(
                trip_id=uuid4(),
                rider=Point(49.82, -97.15),
                pickup_id="not-an-option",
            )

    assert error.value.code == "pickup_not_available"
    assert error.value.status == 422


async def test_detour_sends_existing_pickups_in_order() -> None:
    trip_id = uuid4()
    existing = Location("Existing pickup", 49.83, -97.16)
    new_pickup = Location("New pickup", 49.82, -97.15)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/detours"
        assert json.loads(request.content) == {
            "tripId": str(trip_id),
            "acceptedPickups": [{"lat": 49.83, "lng": -97.16}],
            "newPickup": {"lat": 49.82, "lng": -97.15},
        }
        return httpx.Response(
            200,
            json={"addedSeconds": 180, "position": 1, "totalSeconds": 1500},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        result = await HTTPRequestRoutingService(client).estimate_detour(
            trip_id=trip_id,
            accepted_pickups=[existing],
            new_pickup=new_pickup,
        )

    assert result.added_seconds == 180
    assert result.position == 1
    assert result.total_seconds == 1500


@pytest.mark.parametrize("operation", ["pickup", "detour"])
@pytest.mark.parametrize("failure", ["timeout", "http-error", "invalid-json", "invalid-fields"])
async def test_routing_failures_are_not_successful_quotes(operation: str, failure: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("Routing timed out", request=request)
        if failure == "http-error":
            return httpx.Response(503)
        if failure == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        service = HTTPRequestRoutingService(client)

        with pytest.raises(RoutingUnavailableError):
            if operation == "pickup":
                await service.select_pickup(
                    trip_id=uuid4(),
                    rider=Point(49.82, -97.15),
                    pickup_id="s42",
                )
            else:
                await service.estimate_detour(
                    trip_id=uuid4(),
                    accepted_pickups=[],
                    new_pickup=Location("Pickup", 49.82, -97.15),
                )


@pytest.mark.parametrize(
    "payload",
    [
        {"addedSeconds": -1, "position": 0, "totalSeconds": 900},
        {"addedSeconds": "180", "position": 0, "totalSeconds": 900},
        {"addedSeconds": 180, "position": 1, "totalSeconds": 900},
        {"addedSeconds": 180, "position": 0, "totalSeconds": 100},
    ],
)
async def test_invalid_detour_values_are_rejected(payload: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://routing:8000"
    ) as client:
        with pytest.raises(RoutingUnavailableError):
            await HTTPRequestRoutingService(client).estimate_detour(
                trip_id=uuid4(),
                accepted_pickups=[],
                new_pickup=Location("Pickup", 49.82, -97.15),
            )
