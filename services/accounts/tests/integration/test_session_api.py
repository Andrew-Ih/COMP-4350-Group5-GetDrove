"""POST /auth/refresh and POST /auth/logout (#90), over HTTP against a real PostgreSQL,
checked against contracts/openapi/accounts.json. Ends with the whole of user story #89.

The cookie is Secure and limited to /api/accounts/auth (the gateway's path), so the test
client doesn't send it to http://test/auth/... by itself: tests pass it explicitly, as the
browser would through the gateway.
"""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.domain.email import Email
from accounts.domain.user import User

PASSWORD = "correct horse battery"  # noqa: S105 (a test password)
LOGIN = {"email": "ada@myumanitoba.ca", "password": PASSWORD}


async def account(session: AsyncSession) -> User:
    user = User.register(
        Email.parse("ada@myumanitoba.ca"), Argon2PasswordHasher().hash(PASSWORD), "Ada", "Lovelace"
    )
    user.email_verified_at = datetime.now(UTC)
    await SqlUserRepository(session).add(user)
    await session.commit()
    return user


def cookie_of(response: Response) -> tuple[str, dict[str, str]]:
    """The refresh_token cookie a response sets: its value and attributes (lowercase)."""
    [header] = response.headers.get_list("set-cookie")
    first, *attributes = [part.strip() for part in header.split(";")]
    name, value = first.split("=", 1)
    assert name == "refresh_token"
    parsed = {}
    for attribute in attributes:
        key, _, attribute_value = attribute.partition("=")
        parsed[key.lower()] = attribute_value
    return value.strip('"'), parsed


def with_cookie(value: str) -> dict[str, str]:
    return {"Cookie": f"refresh_token={value}"}


async def log_in(api: AsyncClient) -> str:
    response = await api.post("/auth/login", json=LOGIN)
    assert response.status_code == 200
    return cookie_of(response)[0]


def assert_problem(response: Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    return body


# ---------------------------------------------------------------- POST /auth/refresh


async def test_refreshing_returns_a_new_access_token_and_a_new_cookie(
    api: AsyncClient, session: AsyncSession
) -> None:
    await account(session)
    cookie = await log_in(api)

    response = await api.post("/auth/refresh", headers=with_cookie(cookie))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "tokenType", "expiresIn"}
    assert (body["tokenType"], body["expiresIn"]) == ("Bearer", 900)
    new_cookie, attributes = cookie_of(response)
    assert new_cookie != cookie
    assert new_cookie not in response.text  # never in the body
    assert "httponly" in attributes
    assert "secure" in attributes
    assert attributes["samesite"].lower() == "strict"
    assert attributes["path"] == "/api/accounts/auth"
    assert attributes["max-age"] == str(7 * 24 * 60 * 60)

    me = await api.get("/me", headers={"Authorization": f"Bearer {body['accessToken']}"})
    assert me.status_code == 200


async def test_a_missing_cookie_is_401(api: AsyncClient) -> None:
    assert_problem(await api.post("/auth/refresh"), 401, "invalid_refresh_token")


async def test_an_unknown_cookie_is_401(api: AsyncClient) -> None:
    response = await api.post("/auth/refresh", headers=with_cookie("not-a-real-token"))

    assert_problem(response, 401, "invalid_refresh_token")


async def test_reusing_an_old_cookie_ends_every_session(
    api: AsyncClient, session: AsyncSession
) -> None:
    await account(session)
    old = await log_in(api)
    new, _ = cookie_of(await api.post("/auth/refresh", headers=with_cookie(old)))

    # Someone presents the old (already swapped) copy...
    assert_problem(
        await api.post("/auth/refresh", headers=with_cookie(old)), 401, "invalid_refresh_token"
    )
    # ...so the student's newest cookie stops working too: they log in again.
    assert_problem(
        await api.post("/auth/refresh", headers=with_cookie(new)), 401, "invalid_refresh_token"
    )


# ---------------------------------------------------------------- POST /auth/logout


async def test_logging_out_ends_the_session_and_clears_the_cookie(
    api: AsyncClient, session: AsyncSession
) -> None:
    await account(session)
    cookie = await log_in(api)

    response = await api.post("/auth/logout", headers=with_cookie(cookie))

    assert response.status_code == 204
    assert response.content == b""
    value, attributes = cookie_of(response)
    assert value == ""
    assert attributes["max-age"] == "0"  # tells the browser to delete it now
    # The browser only deletes it if these match how it was set.
    assert attributes["path"] == "/api/accounts/auth"
    assert "secure" in attributes
    assert attributes["samesite"].lower() == "strict"

    assert_problem(
        await api.post("/auth/refresh", headers=with_cookie(cookie)), 401, "invalid_refresh_token"
    )


async def test_logging_out_without_a_session_still_succeeds(api: AsyncClient) -> None:
    response = await api.post("/auth/logout")

    assert response.status_code == 204
    assert cookie_of(response)[1]["max-age"] == "0"


# ---------------------------------------------------------------- the whole story


async def test_stay_logged_in_until_logging_out(api: AsyncClient, session: AsyncSession) -> None:
    """User story #89: stay logged in across visits until you log out."""
    await account(session)
    cookie = await log_in(api)

    # Each visit (or every 15 minutes) the web app swaps the cookie for a new access token.
    for _ in range(3):
        response = await api.post("/auth/refresh", headers=with_cookie(cookie))
        assert response.status_code == 200
        cookie, _ = cookie_of(response)

    assert (await api.post("/auth/logout", headers=with_cookie(cookie))).status_code == 204
    assert_problem(
        await api.post("/auth/refresh", headers=with_cookie(cookie)), 401, "invalid_refresh_token"
    )
