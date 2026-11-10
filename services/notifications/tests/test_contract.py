"""The Notifications API contract (#262): the bell's endpoints exist, need a token, validate
their input, document their errors, and return 501 until #145 implements them."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from notifications.infrastructure.main import create_app

ID = "9a4c2e10-1b7d-4f53-8d3e-6c1f0a2b3c4d"
ENDPOINTS = [("GET", "/"), ("POST", "/read-all"), ("POST", f"/{ID}/read")]


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


def _client(app: Any, headers: dict[str, str] | None = None) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


def test_spec_documents_the_endpoints() -> None:
    assert set(create_app().openapi()["paths"]) >= {"/", "/read-all", "/{notification_id}/read"}


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_endpoints_need_a_token_then_return_501(
    auth: TestAuth, method: str, path: str
) -> None:
    app = create_app()
    auth.install(app)
    async with _client(app) as client:
        anonymous = await client.request(method, path)
        logged_in = await client.request(method, path, headers=auth.headers())

    assert anonymous.status_code == 401
    assert logged_in.status_code == 501


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=many"])
async def test_invalid_limits_are_rejected(auth: TestAuth, query: str) -> None:
    app = create_app()
    auth.install(app)
    async with _client(app, auth.headers()) as client:
        response = await client.get(f"/?{query}")

    assert response.status_code == 422


async def test_notification_id_must_be_a_uuid(auth: TestAuth) -> None:
    app = create_app()
    auth.install(app)
    async with _client(app, auth.headers()) as client:
        response = await client.post("/not-a-uuid/read")

    assert response.status_code == 422


def test_every_error_response_has_its_own_example() -> None:
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
