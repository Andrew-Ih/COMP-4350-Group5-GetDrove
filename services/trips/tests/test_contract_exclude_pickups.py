"""The contract for leaving out rejected pickup points on the trip detail (#292): the rider's
rejected points (#136) are passed to Routing so they're never offered again (#29)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import get_trip_detail
from trips.adapters.api.schemas import MAX_EXCLUDED_PICKUPS
from trips.infrastructure.main import create_app

ID = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
NEAR = "lat=49.8722&lng=-97.1561"


@pytest.fixture
async def client(fake_trip_detail: Any) -> AsyncClient:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    app.dependency_overrides[get_trip_detail] = lambda: fake_trip_detail
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=auth.headers()
    )


@pytest.mark.parametrize(
    ("query", "exclude"),
    [
        (f"{NEAR}&exclude=s42", ["s42"]),
        (f"{NEAR}&exclude=s42&exclude=s45", ["s42", "s45"]),
        (
            "&".join([NEAR, *(f"exclude=s{n}" for n in range(MAX_EXCLUDED_PICKUPS))]),
            [f"s{n}" for n in range(MAX_EXCLUDED_PICKUPS)],
        ),
        (f"{NEAR}", []),  # without it
        ("exclude=s42", ["s42"]),  # passed on, but without lat and lng there are no pickups
    ],
)
async def test_valid_exclude_lists_reach_the_trip_detail(
    client: AsyncClient, fake_trip_detail: Any, query: str, exclude: list[str]
) -> None:
    """Implemented by #30: the list reaches the service as sent."""
    response = await client.get(f"/{ID}?{query}")

    assert response.status_code == 200, response.text
    [call] = fake_trip_detail.calls
    assert call["exclude"] == exclude


@pytest.mark.parametrize(
    "query",
    [
        "&".join([NEAR, *(f"exclude=s{n}" for n in range(MAX_EXCLUDED_PICKUPS + 1))]),
        f"{NEAR}&exclude=",
        f"{NEAR}&exclude={'s' * 65}",
    ],
)
async def test_invalid_exclude_lists_are_rejected(client: AsyncClient, query: str) -> None:
    response = await client.get(f"/{ID}?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


def test_spec_documents_exclude_as_a_repeated_query_parameter() -> None:
    detail = create_app().openapi()["paths"]["/{trip_id}"]["get"]
    [exclude] = [p for p in detail["parameters"] if p["name"] == "exclude"]

    assert exclude["in"] == "query"
    assert exclude["required"] is False
    assert any(option.get("type") == "array" for option in exclude["schema"]["anyOf"])
