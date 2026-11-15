"""The Sprint 2 Trips contract (#262): every new endpoint exists, validates its input,
needs a token and returns 501 until its task implements it."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from trips.adapters.api.dependencies import get_request_seat, get_upcoming_trips
from trips.adapters.api.schemas import AutoAcceptRules, PostTripSeriesRequest, SeatRequestBody
from trips.infrastructure.main import create_app

ID = "5f0b6a52-3c5d-4b6e-9a51-2b8f3a0c9d11"
SERIES = {
    "direction": "to_campus",
    "place": {"label": "Wolseley Ave & Arlington St", "lat": 49.8794, "lng": -97.1663},
    "departureAt": "2026-11-16T13:10:00Z",
    "seatsTotal": 3,
    "weekdays": ["mon", "wed", "fri"],
    "endDate": "2026-12-11",
}
SEAT_REQUEST = {"lat": 49.8722, "lng": -97.1561, "pickupId": "s42"}
RULES = {"enabled": True, "maxDetourMinutes": 5, "minRating": 4.0}

NEW_ENDPOINTS: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", "/series", {"json": SERIES}),
    ("GET", "/mine?when=past", {}),
    ("GET", "/requests/mine", {}),
    ("GET", "/requests/mine?when=past", {}),
    ("GET", "/auto-accept", {}),
    ("PUT", "/auto-accept", {"json": RULES}),
    ("GET", f"/{ID}", {}),
    ("GET", f"/{ID}?lat=49.8722&lng=-97.1561", {}),
    ("POST", f"/{ID}/cancel", {}),
    ("POST", f"/series/{ID}/cancel", {}),
    ("POST", f"/{ID}/requests", {"json": SEAT_REQUEST}),
    ("GET", f"/{ID}/requests", {}),
    ("GET", f"/requests/{ID}", {}),
    ("POST", f"/requests/{ID}/accept", {}),
    ("POST", f"/requests/{ID}/decline", {}),
    ("POST", f"/requests/{ID}/cancel", {}),
]
IMPLEMENTED = {
    ("POST", f"/{ID}/requests"),
    ("POST", f"/requests/{ID}/accept"),
    ("POST", f"/requests/{ID}/decline"),
    ("POST", f"/requests/{ID}/cancel"),
    ("GET", f"/{ID}/requests"),
}
STILL_501 = [e for e in NEW_ENDPOINTS if (e[0], e[1]) not in IMPLEMENTED]


@pytest.fixture
async def client() -> AsyncClient:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    # /mine?when=past reaches the handler before the 501, so it needs a service.
    app.dependency_overrides[get_upcoming_trips] = lambda: object()
    app.dependency_overrides[get_request_seat] = lambda: object()
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=auth.headers()
    )


def test_spec_documents_the_sprint_2_endpoints() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths) >= {
        "/series",
        "/requests/mine",
        "/auto-accept",
        "/{trip_id}/cancel",
        "/series/{series_id}/cancel",
        "/{trip_id}/requests",
        "/requests/{request_id}",
        "/requests/{request_id}/accept",
        "/requests/{request_id}/decline",
        "/requests/{request_id}/cancel",
    }
    detail = paths["/{trip_id}"]["get"]["responses"]["200"]["content"]["application/json"]
    assert detail["schema"] == {"$ref": "#/components/schemas/TripDetail"}


def test_examples_are_valid() -> None:
    assert PostTripSeriesRequest.model_validate(SERIES).weekdays == ["mon", "wed", "fri"]
    assert SeatRequestBody.model_validate(SEAT_REQUEST).pickup_id == "s42"
    assert AutoAcceptRules.model_validate(RULES).max_detour_minutes == 5


@pytest.mark.parametrize(("method", "path", "kwargs"), STILL_501)
async def test_valid_requests_reach_the_not_yet_implemented_handler(
    client: AsyncClient, method: str, path: str, kwargs: dict[str, Any]
) -> None:
    response = await client.request(method, path, **kwargs)

    assert response.status_code == 501, response.text


@pytest.mark.parametrize(("method", "path", "kwargs"), NEW_ENDPOINTS)
async def test_new_endpoints_need_a_token(method: str, path: str, kwargs: dict[str, Any]) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as anonymous:
        response = await anonymous.request(method, path, **kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "change",
    [
        {"weekdays": []},
        {"weekdays": ["sat"]},
        {"weekdays": ["mon", "tue", "wed", "thu", "fri", "mon"]},
        {"weekdays": ["mon", "mon"]},
        {"endDate": "not-a-date"},
        {"seatsTotal": 7},
    ],
)
async def test_invalid_series_are_rejected(client: AsyncClient, change: dict[str, Any]) -> None:
    response = await client.post("/series", json={**SERIES, **change})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "change",
    [{"maxDetourMinutes": 31}, {"maxDetourMinutes": -1}, {"minRating": 0.5}, {"minRating": 5.5}],
)
async def test_invalid_auto_accept_rules_are_rejected(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    response = await client.put("/auto-accept", json={**RULES, **change})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "change", [{"pickupId": ""}, {"lat": 91}, {"lng": -181}, {"pickupId": None}]
)
async def test_invalid_seat_requests_are_rejected(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    response = await client.post(f"/{ID}/requests", json={**SEAT_REQUEST, **change})

    assert response.status_code == 422


@pytest.mark.parametrize("query", ["lat=49.87", "lng=-97.15"])
async def test_trip_detail_needs_lat_and_lng_together(client: AsyncClient, query: str) -> None:
    response = await client.get(f"/{ID}?{query}")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_unknown_when_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/requests/mine?when=tomorrow")

    assert response.status_code == 422


async def test_fixed_paths_are_not_read_as_a_trip_id(client: AsyncClient) -> None:
    """/auto-accept and /requests/mine must not be matched by /{trip_id} (a 422 for "not a
    UUID" would mean they were)."""
    for path in ["/auto-accept", "/requests/mine"]:
        response = await client.get(path)
        assert response.status_code == 501, path


def test_trip_detail_has_the_vehicle_for_accepted_riders() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "vehicle" in schemas["TripDetail"]["properties"]
    assert "plate" in schemas["TripVehicle"]["properties"]
