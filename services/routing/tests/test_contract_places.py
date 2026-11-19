"""The places contract (#257): finding your area by typing an address. The endpoint exists,
needs a login and validates what was typed. It returns 501 until it's implemented."""

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from routing.adapters.api.schemas import PlaceSearchRequest, PlaceSearchResponse
from routing.infrastructure.main import create_app


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


@pytest.fixture
async def client(auth: TestAuth) -> AsyncClient:
    app = create_app()
    auth.install(app)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_spec_documents_the_places_endpoint() -> None:
    spec = create_app().openapi()
    operation = spec["paths"]["/places"]["post"]

    assert set(operation["responses"]) >= {"200", "401", "422", "503"}
    assert "geocoding_unavailable" in operation["responses"]["503"]["description"]


def test_what_was_typed_is_trimmed() -> None:
    assert PlaceSearchRequest.model_validate({"query": "  750 Osborne St "}).query == (
        "750 Osborne St"
    )


@pytest.mark.parametrize("query", ["", "  ", "ab", "x" * 201])
def test_too_short_or_too_long_is_refused(query: str) -> None:
    with pytest.raises(ValueError):
        PlaceSearchRequest.model_validate({"query": query})


def test_at_most_five_places_come_back() -> None:
    place = {"label": "Polo Park", "lat": 49.88, "lng": -97.2}

    assert len(PlaceSearchResponse.model_validate({"places": [place] * 5}).places) == 5
    with pytest.raises(ValueError):
        PlaceSearchResponse.model_validate({"places": [place] * 6})


async def test_a_login_is_needed(client: AsyncClient) -> None:
    response = await client.post("/places", json={"query": "750 Osborne St"})

    assert response.status_code == 401


async def test_a_short_query_is_422(client: AsyncClient, auth: TestAuth) -> None:
    response = await client.post("/places", json={"query": "ab"}, headers=auth.headers())

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"
