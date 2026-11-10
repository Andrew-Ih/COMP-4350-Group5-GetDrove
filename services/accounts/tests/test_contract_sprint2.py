"""The Sprint 2 Accounts contract (#262): driver applications, admin approval, profiles and
the internal lookups exist, check who's calling, validate input, and return 501 until
implemented."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from accounts.adapters.api.schemas import RejectDriverRequest, Vehicle
from accounts.infrastructure.main import create_app
from common_security.testing import TestAuth

ID = "0c8d6a1e-7b44-4f0e-8f61-6a2a9d3c5e77"
VEHICLE = {"make": "Honda", "model": "Civic", "colour": "Blue", "plate": "ABC123"}
FILES = {
    "licence": ("licence.pdf", b"%PDF-1.7", "application/pdf"),
    "insurance": ("insurance.png", b"\x89PNG", "image/png"),
}

DRIVER_ENDPOINTS: list[tuple[str, str, dict[str, Any]]] = [
    ("GET", "/me/driver", {}),
    ("PUT", "/me/driver/documents", {"files": FILES}),
    ("GET", "/me/driver/documents/licence", {}),
    ("PUT", "/me/driver/vehicle", {"json": VEHICLE}),
    ("GET", f"/users/{ID}/profile", {}),
]
ADMIN_ENDPOINTS: list[tuple[str, str, dict[str, Any]]] = [
    ("GET", "/admin/drivers", {}),
    ("GET", "/admin/drivers?status=rejected", {}),
    ("GET", f"/admin/drivers/{ID}/documents/insurance", {}),
    ("POST", f"/admin/drivers/{ID}/approve", {}),
    ("POST", f"/admin/drivers/{ID}/reject", {"json": {"reason": "Expired insurance."}}),
]


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


def _client(auth: TestAuth, roles: list[str] | None = None) -> AsyncClient:
    app = create_app()
    auth.install(app)
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth.headers(roles=roles),
    )


def test_spec_documents_the_sprint_2_endpoints() -> None:
    assert set(create_app().openapi()["paths"]) >= {
        "/me/driver",
        "/me/driver/documents",
        "/me/driver/documents/{kind}",
        "/me/driver/vehicle",
        "/admin/drivers",
        "/admin/drivers/{user_id}/documents/{kind}",
        "/admin/drivers/{user_id}/approve",
        "/admin/drivers/{user_id}/reject",
        "/users/{user_id}/profile",
        "/internal/users",
        "/internal/contacts",
    }


def test_examples_are_valid() -> None:
    assert Vehicle.model_validate(VEHICLE).plate == "ABC123"
    assert RejectDriverRequest.model_validate({"reason": "Blurry photo."}).reason


@pytest.mark.parametrize(("method", "path", "kwargs"), DRIVER_ENDPOINTS)
async def test_driver_endpoints_reach_the_not_yet_implemented_handler(
    auth: TestAuth, method: str, path: str, kwargs: dict[str, Any]
) -> None:
    async with _client(auth) as client:
        response = await client.request(method, path, **kwargs)

    assert response.status_code == 501, response.text


@pytest.mark.parametrize(("method", "path", "kwargs"), DRIVER_ENDPOINTS + ADMIN_ENDPOINTS)
async def test_they_need_a_token(method: str, path: str, kwargs: dict[str, Any]) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as anonymous:
        response = await anonymous.request(method, path, **kwargs)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "kwargs"), ADMIN_ENDPOINTS)
async def test_admin_endpoints_need_the_admin_role(
    auth: TestAuth, method: str, path: str, kwargs: dict[str, Any]
) -> None:
    async with _client(auth, roles=["user"]) as student:
        refused = await student.request(method, path, **kwargs)
    async with _client(auth, roles=["user", "admin"]) as admin:
        allowed = await admin.request(method, path, **kwargs)

    assert refused.status_code == 403
    assert refused.json()["code"] == "forbidden"
    assert allowed.status_code == 501, allowed.text


@pytest.mark.parametrize(
    "change",
    [
        {"plate": "A"},
        {"plate": "ABC 123"},
        {"plate": "ABCDEFGH9"},
        {"make": ""},
        {"colour": "x" * 31},
    ],
)
async def test_invalid_vehicles_are_rejected(auth: TestAuth, change: dict[str, Any]) -> None:
    async with _client(auth) as client:
        response = await client.put("/me/driver/vehicle", json={**VEHICLE, **change})

    assert response.status_code == 422


async def test_both_documents_are_required(auth: TestAuth) -> None:
    async with _client(auth) as client:
        response = await client.put("/me/driver/documents", files={"licence": FILES["licence"]})

    assert response.status_code == 422


async def test_unknown_document_kind_is_rejected(auth: TestAuth) -> None:
    async with _client(auth) as client:
        response = await client.get("/me/driver/documents/passport")

    assert response.status_code == 422


async def test_reject_needs_a_reason(auth: TestAuth) -> None:
    async with _client(auth, roles=["user", "admin"]) as admin:
        response = await admin.post(f"/admin/drivers/{ID}/reject", json={"reason": ""})

    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/internal/users", "/internal/contacts"])
async def test_internal_lookups_take_1_to_50_ids(path: str) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        one = await client.get(path, params={"ids": [ID]})
        none = await client.get(path)
        too_many = await client.get(path, params={"ids": [ID] * 51})
        not_uuid = await client.get(path, params={"ids": ["nope"]})

    assert one.status_code == 501
    assert none.status_code == 422
    assert too_many.status_code == 422
    assert not_uuid.status_code == 422


async def test_admin_list_has_no_none_status(auth: TestAuth) -> None:
    async with _client(auth, roles=["user", "admin"]) as admin:
        response = await admin.get("/admin/drivers", params={"status": "none"})

    assert response.status_code == 422


def test_approving_documents_a_missing_vehicle() -> None:
    approve = create_app().openapi()["paths"]["/admin/drivers/{user_id}/approve"]["post"]

    assert "vehicle_missing" in approve["responses"]["409"]["description"]


def test_internal_users_include_the_drivers_vehicle() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "vehicle" in schemas["InternalUser"]["properties"]
    assert "email" not in schemas["InternalUser"]["properties"]
