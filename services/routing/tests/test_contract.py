"""The Routing API contract (#108)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from routing.infrastructure.main import create_app

TRIP_ID = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
POINT = {"lat": 49.88, "lng": -97.14}


@pytest.fixture
async def client() -> AsyncClient:
    """A client logged in as a test user (common_security.testing)."""
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=auth.headers()
    )


def test_spec_documents_the_sprint_1_endpoints() -> None:
    paths = set(create_app().openapi()["paths"])

    assert paths >= {"/internal/routes", "/internal/matches", "/trips/{trip_id}/geometry"}


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        # Implemented: POST /internal/routes (#24, test_compute_route_api.py) and
        # GET /trips/{trip_id}/geometry (#123, test_route_geometry_api.py).
        ("POST", "/internal/matches", {"json": {"rider": POINT, "tripIds": [TRIP_ID]}}),
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


def test_every_error_response_has_its_own_example() -> None:
    """#230: errors used to share one example from the Problem schema, so the docs showed
    the same body for every error. Each one now shows its own status and code."""
    for path, operations in create_app().openapi()["paths"].items():
        for method, operation in operations.items():
            for status, response in operation["responses"].items():
                if not status.isdigit() or int(status) < 400:
                    continue
                content = response["content"]["application/json"]
                where = f"{method.upper()} {path} {status}"
                assert content["schema"] == {"$ref": "#/components/schemas/Problem"}, where
                example = content["example"]
                assert example["status"] == int(status), where
                assert f"`{example['code']}" in response["description"], where
