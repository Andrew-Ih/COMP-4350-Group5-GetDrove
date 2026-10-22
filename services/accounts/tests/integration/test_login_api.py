"""POST /auth/login and GET /me (#6), over HTTP against a real PostgreSQL, checked against
contracts/openapi/accounts.json. Ends with the whole journey: sign up, verify, log in, /me."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import outbox, refresh_tokens
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.domain.email import Email
from accounts.domain.user import User
from accounts.domain.verification import hash_token

PASSWORD = "correct horse battery"  # noqa: S105 (a test password)
LOGIN = {"email": "ada@myumanitoba.ca", "password": PASSWORD}


async def account(session: AsyncSession, *, verified: bool = True) -> User:
    user = User.register(
        Email.parse("ada@myumanitoba.ca"), Argon2PasswordHasher().hash(PASSWORD), "Ada", "Lovelace"
    )
    user.email_verified_at = datetime.now(UTC) if verified else None
    await SqlUserRepository(session).add(user)
    await session.commit()
    return user


def assert_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


def refresh_cookie(response: Response) -> tuple[str, dict[str, str]]:
    """The refresh_token cookie's value and its attributes (lowercase names)."""
    [header] = response.headers.get_list("set-cookie")
    first, *attributes = [part.strip() for part in header.split(";")]
    name, value = first.split("=", 1)
    assert name == "refresh_token"
    parsed = {}
    for attribute in attributes:
        key, _, attribute_value = attribute.partition("=")
        parsed[key.lower()] = attribute_value
    return value, parsed


# ---------------------------------------------------------------- POST /auth/login


async def test_logging_in_returns_the_contracts_token_response(
    api: AsyncClient, session: AsyncSession
) -> None:
    await account(session)

    response = await api.post("/auth/login", json=LOGIN)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "tokenType", "expiresIn"}  # no refresh token
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == 900


async def test_logging_in_sets_a_locked_down_refresh_cookie(
    api: AsyncClient, session: AsyncSession
) -> None:
    user = await account(session)

    response = await api.post("/auth/login", json=LOGIN)

    value, attributes = refresh_cookie(response)
    assert value not in response.text  # never in the body
    assert "httponly" in attributes
    assert "secure" in attributes
    assert attributes["samesite"].lower() == "strict"
    assert attributes["path"] == "/api/accounts/auth"
    assert attributes["max-age"] == str(7 * 24 * 60 * 60)

    session.expire_all()
    [row] = (await session.execute(select(refresh_tokens))).all()
    assert row.user_id == user.id
    assert row.token_hash == hash_token(value)  # only the hash is stored


@pytest.mark.parametrize(
    "login",
    [
        {"email": "ada@myumanitoba.ca", "password": "wrong password"},
        {"email": "nobody@myumanitoba.ca", "password": PASSWORD},
        {"email": "ada@gmail.com", "password": PASSWORD},
    ],
)
async def test_a_wrong_email_or_password_is_one_401(
    api: AsyncClient, session: AsyncSession, login: dict[str, str]
) -> None:
    await account(session)

    response = await api.post("/auth/login", json=login)

    body = assert_problem(response, 401, "invalid_credentials")
    assert (body["title"], body["detail"]) == (
        "Wrong email or password",
        "Wrong email or password.",
    )
    assert "set-cookie" not in response.headers


async def test_an_unverified_account_is_403(api: AsyncClient, session: AsyncSession) -> None:
    await account(session, verified=False)

    response = await api.post("/auth/login", json=LOGIN)

    assert_problem(response, 403, "email_not_verified")
    assert "set-cookie" not in response.headers


async def test_a_missing_password_is_invalid_input(api: AsyncClient) -> None:
    response = await api.post("/auth/login", json={"email": "ada@myumanitoba.ca", "password": ""})

    body = assert_problem(response, 422, "invalid_input")
    assert [e["field"] for e in body["errors"]] == ["password"]


# ---------------------------------------------------------------- GET /me


async def test_me_returns_the_logged_in_user(api: AsyncClient, session: AsyncSession) -> None:
    user = await account(session)
    token = (await api.post("/auth/login", json=LOGIN)).json()["accessToken"]

    response = await api.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "ada@myumanitoba.ca",
        "firstName": "Ada",
        "lastName": "Lovelace",
        "emailVerified": True,
        "roles": ["user"],
    }


async def test_me_without_a_token_is_401(api: AsyncClient) -> None:
    response = await api.get("/me")

    assert_problem(response, 401, "unauthorized")
    assert response.headers["www-authenticate"] == "Bearer"


# ---------------------------------------------------------------- the whole journey


async def test_sign_up_verify_log_in_and_see_yourself(
    api: AsyncClient, session: AsyncSession
) -> None:
    """User stories #2 and #89 end to end."""
    signup = {**LOGIN, "firstName": "Ada", "lastName": "Lovelace"}
    assert (await api.post("/auth/signup", json=signup)).status_code == 201

    # Before verifying, login is refused.
    assert_problem(await api.post("/auth/login", json=LOGIN), 403, "email_not_verified")

    # "Click" the link from the verification email.
    [envelope] = (await session.execute(select(outbox.c.envelope))).scalars()
    token = envelope["payload"]["verificationToken"]
    assert (await api.post("/auth/verify", json={"token": token})).status_code == 204

    login = await api.post("/auth/login", json=LOGIN)
    assert login.status_code == 200
    me = await api.get("/me", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})
    assert me.json()["email"] == "ada@myumanitoba.ca"
    assert me.json()["emailVerified"] is True
