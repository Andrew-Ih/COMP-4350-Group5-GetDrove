"""The Sprint 2 Routing contract (#262): pickup points and detours exist, validate their
input and return 501 until implemented (#29, #30, #36, #38)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from routing.adapters.api.schemas import DetourRequest, PickupPointsRequest, RouteRequest
from routing.infrastructure.main import create_app

TRIP = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
PICKUPS = {"tripId": TRIP, "rider": {"lat": 49.8722, "lng": -97.1561}}
DETOUR = {
    "tripId": TRIP,
    "acceptedPickups": [{"lat": 49.87, "lng": -97.146}],
    "newPickup": {"lat": 49.86, "lng": -97.148},
}


@pytest.fixture
async def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


def test_spec_documents_the_sprint_2_endpoints() -> None:
    assert set(create_app().openapi()["paths"]) >= {
        "/internal/pickup-points",
        "/internal/detours",
    }


def test_limit_defaults_to_three() -> None:
    assert PickupPointsRequest.model_validate(PICKUPS).limit == 3


def test_routes_still_accept_the_sprint_1_body() -> None:
    """Trips sends driverId and direction from Sprint 2; older callers still work."""
    route = RouteRequest.model_validate(
        {
            "tripId": TRIP,
            "origin": {"lat": 49.88, "lng": -97.17},
            "destination": {"lat": 49.81, "lng": -97.14},
        }
    )

    assert route.driver_id is None
    assert route.direction is None


@pytest.mark.parametrize(
    ("path", "body"), [("/internal/pickup-points", PICKUPS), ("/internal/detours", DETOUR)]
)
async def test_valid_requests_reach_the_not_yet_implemented_handler(
    client: AsyncClient, path: str, body: dict[str, Any]
) -> None:
    response = await client.post(path, json=body)

    assert response.status_code == 501, response.text


@pytest.mark.parametrize("change", [{"limit": 0}, {"limit": 6}, {"rider": {"lat": 91, "lng": 0}}])
async def test_invalid_pickup_requests_are_rejected(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    response = await client.post("/internal/pickup-points", json={**PICKUPS, **change})

    assert response.status_code == 422


async def test_more_than_six_accepted_pickups_is_rejected(client: AsyncClient) -> None:
    body = {**DETOUR, "acceptedPickups": [{"lat": 49.87, "lng": -97.146}] * 7}

    response = await client.post("/internal/detours", json=body)

    assert response.status_code == 422
    assert DetourRequest.model_validate(DETOUR).new_pickup.lat == 49.86
