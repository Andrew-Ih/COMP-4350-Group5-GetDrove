"""POST /api/routing/places (#257) through the app, with a fake place finder."""

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from routing.domain.errors import GeocodingUnavailableError
from routing.domain.places import Area, Place
from routing.domain.values import LatLng
from routing.infrastructure.main import create_app


class FakeFinder:
    def __init__(self, places: list[Place] | None = None, down: bool = False) -> None:
        self.places = places or []
        self.down = down
        self.queries: list[str] = []

    async def find(self, query: str, area: Area, limit: int) -> list[Place]:
        self.queries.append(query)
        if self.down:
            raise GeocodingUnavailableError()
        return self.places


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


def client_for(finder: FakeFinder, auth: TestAuth) -> AsyncClient:
    app = create_app()
    auth.install(app)
    app.state.place_finder = finder
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_it_returns_the_matches(auth: TestAuth) -> None:
    finder = FakeFinder([Place("750 Osborne Street, Fort Rouge", LatLng(49.8664, -97.1386))])

    response = await client_for(finder, auth).post(
        "/places", json={"query": " 750 Osborne St "}, headers=auth.headers()
    )

    assert response.status_code == 200
    assert response.json() == {
        "places": [{"label": "750 Osborne Street, Fort Rouge", "lat": 49.8664, "lng": -97.1386}]
    }
    assert finder.queries == ["750 Osborne St"]  # trimmed


async def test_nothing_found_is_an_empty_list(auth: TestAuth) -> None:
    response = await client_for(FakeFinder(), auth).post(
        "/places", json={"query": "nowhere at all"}, headers=auth.headers()
    )

    assert response.status_code == 200
    assert response.json() == {"places": []}


async def test_lookup_down_is_503(auth: TestAuth) -> None:
    response = await client_for(FakeFinder(down=True), auth).post(
        "/places", json={"query": "750 Osborne St"}, headers=auth.headers()
    )

    assert response.status_code == 503
    assert response.json()["code"] == "geocoding_unavailable"


async def test_the_address_isnt_logged(auth: TestAuth, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    await client_for(FakeFinder(), auth).post(
        "/places", json={"query": "750 Osborne St"}, headers=auth.headers()
    )

    assert "Osborne" not in caplog.text


async def test_a_rejected_query_isnt_echoed_back(auth: TestAuth) -> None:
    response = await client_for(FakeFinder(), auth).post(
        "/places", json={"query": "x" * 201}, headers=auth.headers()
    )

    assert response.status_code == 422
    assert "xxxx" not in response.text
