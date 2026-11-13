"""The Sprint 2 Payments contract (#262): saved cards exist and need a token."""

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from payments.infrastructure.main import create_app

USER = "0c8d6a1e-7b44-4f0e-8f61-6a2a9d3c5e77"


def test_spec_documents_the_sprint_2_endpoints() -> None:
    assert set(create_app().openapi()["paths"]) >= {
        "/setup-intent",
        "/methods",
        "/internal/customers/{user_id}/card",
    }


@pytest.mark.parametrize(("method", "path"), [("POST", "/setup-intent"), ("GET", "/methods")])
async def test_card_endpoints_need_a_token(method: str, path: str) -> None:
    auth = TestAuth()
    app = create_app()
    auth.install(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        anonymous = await client.request(method, path)

    assert anonymous.status_code == 401


async def test_card_status_takes_a_user_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        invalid = await client.get("/internal/customers/not-a-uuid/card")

    assert invalid.status_code == 422
