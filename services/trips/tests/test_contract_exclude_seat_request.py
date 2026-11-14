"""The contract for leaving out rejected pickup points when requesting a seat (#299): the
same `exclude` the trip detail was loaded with (#292), so a point offered after the rider
rejected others (#136) still passes the pickup check (#137)."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from trips.adapters.api.schemas import MAX_EXCLUDED_PICKUPS, SeatRequestBody
from trips.infrastructure.main import create_app

ID = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
BODY: dict[str, Any] = {"lat": 49.8722, "lng": -97.1561, "pickupId": "s50"}


@pytest.fixture
async def client() -> AsyncClient:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=auth.headers()
    )


@pytest.mark.parametrize(
    "exclude",
    [
        ["s42"],
        ["s42", "s45"],
        [f"s{n}" for n in range(MAX_EXCLUDED_PICKUPS)],
        [],
    ],
)
async def test_valid_exclude_lists_reach_the_not_yet_implemented_handler(
    client: AsyncClient, exclude: list[str]
) -> None:
    response = await client.post(f"/{ID}/requests", json={**BODY, "exclude": exclude})

    assert response.status_code == 501, response.text


async def test_exclude_is_optional(client: AsyncClient) -> None:
    response = await client.post(f"/{ID}/requests", json=BODY)

    assert response.status_code == 501, response.text
    assert SeatRequestBody.model_validate(BODY).exclude == []


@pytest.mark.parametrize(
    "exclude",
    [
        [f"s{n}" for n in range(MAX_EXCLUDED_PICKUPS + 1)],
        [""],
        ["s" * 65],
    ],
)
async def test_invalid_exclude_lists_are_rejected(client: AsyncClient, exclude: list[str]) -> None:
    response = await client.post(f"/{ID}/requests", json={**BODY, "exclude": exclude})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


def test_spec_documents_exclude_as_an_optional_list() -> None:
    schema = create_app().openapi()["components"]["schemas"]["SeatRequestBody"]

    assert "exclude" not in schema.get("required", [])
    assert schema["properties"]["exclude"]["type"] == "array"
    assert schema["properties"]["exclude"]["maxItems"] == MAX_EXCLUDED_PICKUPS
