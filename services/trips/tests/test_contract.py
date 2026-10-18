"""The Trips API contract (#108): routes exist, validate their input, and are documented."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import get_post_trip
from trips.adapters.api.schemas import PostTripRequest
from trips.domain.values import Direction, Location
from trips.infrastructure.main import create_app
from trips.adapters.api.dependencies import get_upcoming_trips

VALID_TRIP = {
    "direction": "to_campus",
    "place": {"label": "Wolseley Ave & Arlington St", "lat": 49.8794, "lng": -97.1663},
    "departureAt": "2026-10-20T13:10:00Z",
    "seatsTotal": 3,
}
SEARCH = {"lat": 49.88, "lng": -97.14, "direction": "to_campus", "time": "2026-10-20T13:30:00Z"}


@pytest.fixture
async def client() -> AsyncClient:
    """A test client that can validate requests without starting PostgreSQL."""
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    def fake_post_trip() -> object:
        return object()

    app.dependency_overrides[get_post_trip] = fake_post_trip

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(),
    )


def test_spec_documents_the_sprint_1_endpoints() -> None:
    spec: dict[str, Any] = create_app().openapi()

    assert set(spec["paths"]) >= {"/", "/mine", "/search", "/{trip_id}"}
    post = spec["paths"]["/"]["post"]
    assert {"201", "401", "422", "503"} <= set(post["responses"])
    assert "Trip" in spec["components"]["schemas"]
    assert "HTTPBearer" in spec["components"]["securitySchemes"]


def test_example_request_is_valid() -> None:
    assert PostTripRequest.model_validate(VALID_TRIP).seats_total == 3


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        
        ("GET", "/search", {"params": SEARCH}),
        ("GET", "/5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11", {}),
    ],
)
async def test_valid_requests_reach_the_not_yet_implemented_handler(
    client: AsyncClient, method: str, path: str, kwargs: dict[str, Any]
) -> None:
    response = await client.request(method, path, **kwargs)

    assert response.status_code == 501


@pytest.mark.parametrize(
    "change",
    [
        {"seatsTotal": 7},
        {"seatsTotal": 0},
        {"direction": "to_downtown"},
        {"departureAt": "2026-10-20T13:10:00"},  # no timezone
        {"place": {"label": "", "lat": 49.88, "lng": -97.14}},
    ],
)
async def test_invalid_trips_are_rejected(client: AsyncClient, change: dict[str, Any]) -> None:
    response = await client.post("/", json={**VALID_TRIP, **change})

    assert response.status_code == 422


async def test_search_requires_location_direction_and_time(client: AsyncClient) -> None:
    for missing in SEARCH:
        params = {key: value for key, value in SEARCH.items() if key != missing}
        response = await client.get("/search", params=params)
        assert response.status_code == 422, missing


async def test_trip_id_must_be_a_uuid(client: AsyncClient) -> None:
    response = await client.get("/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize("method,path", [("GET", "/mine"), ("POST", "/")])
async def test_requests_without_a_valid_token_are_rejected(method: str, path: str) -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as anonymous:
        missing = await anonymous.request(method, path, json=VALID_TRIP)
        invalid = await anonymous.request(
            method, path, json=VALID_TRIP, headers={"Authorization": "Bearer not-a-jwt"}
        )

    assert missing.status_code == 401
    assert missing.json()["code"] == "unauthorized"
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "invalid_token"


async def test_expired_token_is_rejected() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/mine", headers=auth.headers(expires_in=-120))

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


async def test_post_trip_uses_injected_service() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    from trips.adapters.api.dependencies import get_post_trip

    class FakePostTripService:
        def __init__(self) -> None:
            self.called = False

        async def execute(self, **kwargs: Any) -> Any:
            self.called = True

            assert kwargs["direction"] == Direction.TO_CAMPUS
            assert isinstance(kwargs["place"], Location)
            assert kwargs["seats_total"] == 3

            departure = datetime.now(UTC) + timedelta(days=2)
            place = kwargs["place"]

            return SimpleNamespace(
                id=uuid4(),
                driver_id=kwargs["driver_id"],
                direction=kwargs["direction"],
                origin=place,
                destination=place,
                departure_at=departure,
                estimated_arrival_at=departure + timedelta(minutes=20),
                duration_seconds=1200,
                distance_meters=5000,
                seats_total=3,
                seats_available=3,
                status="scheduled",
            )

    fake_service = FakePostTripService()
    app.dependency_overrides[get_post_trip] = lambda: fake_service

    valid_trip = {
        **VALID_TRIP,
        "departureAt": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(),
    ) as client:
        response = await client.post("/", json=valid_trip)

    assert response.status_code == 201, response.text
    assert fake_service.called


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



@pytest.mark.asyncio
async def test_my_trips_returns_upcoming_trips() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    driver_id = uuid4()
    departure = datetime.now(UTC) + timedelta(days=2)
    place = Location(
        label="Pembina Highway",
        lat=49.82,
        lng=-97.15,
    )

    expected_trip = SimpleNamespace(
        id=uuid4(),
        driver_id=driver_id,
        direction=Direction.TO_CAMPUS,
        origin=place,
        destination=place,
        departure_at=departure,
        estimated_arrival_at=departure + timedelta(minutes=20),
        duration_seconds=1200,
        distance_meters=5000,
        seats_total=3,
        seats_available=3,
        status="scheduled",
    )

    class FakeUpcomingTripsService:
        async def execute(self, *, driver_id):
            return [expected_trip]

    app.dependency_overrides[get_upcoming_trips] = (
        lambda: FakeUpcomingTripsService()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(),
    ) as client:
        response = await client.get("/mine?role=driver")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(expected_trip.id)
    assert body[0]["driver_id"] == str(expected_trip.driver_id)
    assert body[0]["origin"]["label"] == "Pembina Highway"
    assert body[0]["destination"]["label"] == "Pembina Highway"
    assert body[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_my_trips_returns_empty_list() -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)

    class FakeUpcomingTripsService:
        async def execute(self, *, driver_id):
            return []

    app.dependency_overrides[get_upcoming_trips] = (
        lambda: FakeUpcomingTripsService()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(),
    ) as client:
        response = await client.get("/mine")

    assert response.status_code == 200, response.text
    assert response.json() == []