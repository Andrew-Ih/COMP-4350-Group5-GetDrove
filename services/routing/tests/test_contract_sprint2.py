"""The Sprint 2 Routing contract (#262): pickup points and detours exist and validate their
input. Detours return 501 until implemented (#36, #38); pickup points are implemented (#29)
and tested with a real database in test_pickup_points_api.py."""

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


async def test_valid_detour_requests_reach_the_not_yet_implemented_handler(
    client: AsyncClient,
) -> None:
    response = await client.post("/internal/detours", json=DETOUR)

    assert response.status_code == 501, response.text


async def test_more_than_six_accepted_pickups_is_rejected(client: AsyncClient) -> None:
    body = {**DETOUR, "acceptedPickups": [{"lat": 49.87, "lng": -97.146}] * 7}

    response = await client.post("/internal/detours", json=body)

    assert response.status_code == 422
    assert DetourRequest.model_validate(DETOUR).new_pickup.lat == 49.86
