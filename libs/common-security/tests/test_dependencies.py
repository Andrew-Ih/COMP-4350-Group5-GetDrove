"""current_user and require_role through a small FastAPI app."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from common_security import CurrentUser
from common_security.dependencies import AuthenticatedUser, require_role
from common_security.testing import TestAuth
from common_web.app import install


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


@pytest.fixture
async def client(auth: TestAuth) -> AsyncClient:
    app = FastAPI()
    install(app, service="test")
    auth.install(app)

    @app.get("/me")
    async def me(user: AuthenticatedUser) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.get("/admin")
    async def admin(user: Annotated[CurrentUser, Depends(require_role("admin"))]) -> dict[str, str]:
        return {"id": str(user.id)}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_valid_token_reaches_the_endpoint(client: AsyncClient, auth: TestAuth) -> None:
    response = await client.get("/me", headers=auth.headers())

    assert response.status_code == 200
    assert response.json() == {"id": str(auth.user_id)}


async def test_missing_token_is_401_problem_details(client: AsyncClient) -> None:
    response = await client.get("/me")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["code"] == "unauthorized"


async def test_expired_token_is_401_token_expired(client: AsyncClient, auth: TestAuth) -> None:
    response = await client.get("/me", headers=auth.headers(expires_in=-120))

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


async def test_bad_token_is_401_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_missing_role_is_403(client: AsyncClient, auth: TestAuth) -> None:
    response = await client.get("/admin", headers=auth.headers(roles=["user"]))

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_required_role_is_allowed(client: AsyncClient, auth: TestAuth) -> None:
    response = await client.get("/admin", headers=auth.headers(roles=["user", "admin"]))

    assert response.status_code == 200
