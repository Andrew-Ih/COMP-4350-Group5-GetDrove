"""The Routing API contract (#108)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from routing.infrastructure.main import create_app

TRIP_ID = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
POINT = {"lat": 49.88, "lng": -97.14}


@pytest.fixture
async def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


def test_spec_documents_the_sprint_1_endpoints() -> None:
    paths = set(create_app().openapi()["paths"])

    assert paths >= {"/internal/routes", "/internal/matches", "/trips/{trip_id}/geometry"}


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        (
            "POST",
            "/internal/routes",
            {"json": {"tripId": TRIP_ID, "origin": POINT, "destination": POINT}},
        ),
        ("POST", "/internal/matches", {"json": {"rider": POINT, "tripIds": [TRIP_ID]}}),
        ("GET", f"/trips/{TRIP_ID}/geometry", {}),
    ],
)
async def test_valid_requests_reach_the_not_yet_implemented_handler(
    client: AsyncClient, method: str, path: str, kwargs: dict[str, Any]
) -> None:
    response = await client.request(method, path, **kwargs)

    assert response.status_code == 501


async def test_invalid_coordinates_are_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/matches", json={"rider": {"lat": 120, "lng": -97.14}, "tripIds": []}
    )

    assert response.status_code == 422
