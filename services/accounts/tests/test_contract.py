"""The Accounts API contract (#108): routes exist, validate their input, and are documented."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from accounts.infrastructure.main import create_app
from common_security.testing import TestAuth

SIGNUP = {
    "email": "ada.lovelace@myumanitoba.ca",
    "password": "correct horse battery",
    "firstName": "Ada",
    "lastName": "Lovelace",
}


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

    assert paths >= {
        "/auth/signup",
        "/auth/verify",
        "/auth/resend-verification",
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/me",
        "/.well-known/jwks.json",
    }


# Every endpoint is implemented now (#4, #5, #6, #90); their behaviour is tested over HTTP
# against a real database in tests/integration/.


@pytest.mark.parametrize(
    "change",
    [
        {"password": "short"},
        {"firstName": ""},
        {"lastName": ""},
        {"email": ""},
    ],
)
async def test_invalid_signups_are_rejected(client: AsyncClient, change: dict[str, Any]) -> None:
    response = await client.post("/auth/signup", json={**SIGNUP, **change})

    assert response.status_code == 422
