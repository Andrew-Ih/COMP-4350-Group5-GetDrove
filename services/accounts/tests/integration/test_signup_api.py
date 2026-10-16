"""POST /auth/signup (#4), over HTTP against a real PostgreSQL, checked against
contracts/openapi/accounts.json. Ends with the whole of user story #2: sign up, then verify."""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import outbox, users

SIGNUP = {
    "email": "Ada.Lovelace@MyUManitoba.ca",
    "password": "correct horse battery",
    "firstName": "Ada",
    "lastName": "Lovelace",
}


def assert_problem(response: Response, status: int, code: str, fields: list[str]) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["code"] == code
    assert [e["field"] for e in body.get("errors") or []] == fields


async def outbox_events(session: AsyncSession) -> list[dict[str, Any]]:
    session.expire_all()
    rows = await session.execute(select(outbox.c.envelope).order_by(outbox.c.id))
    return [row.envelope for row in rows]


async def test_signing_up_returns_201_with_the_contracts_body(
    api: AsyncClient, session: AsyncSession
) -> None:
    response = await api.post("/auth/signup", json=SIGNUP)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "emailVerified"}
    assert body["email"] == "ada.lovelace@myumanitoba.ca"
    assert body["emailVerified"] is False

    row = (await session.execute(select(users).where(users.c.id == body["id"]))).one()
    assert row.password_hash.startswith("$argon2id$")
    assert SIGNUP["password"] not in row.password_hash
    assert row.email_verified_at is None


async def test_signing_up_asks_notifications_for_the_verification_email(
    api: AsyncClient, session: AsyncSession
) -> None:
    body = (await api.post("/auth/signup", json=SIGNUP)).json()

    [event] = await outbox_events(session)
    assert event["type"] == "UserRegistered"
    assert event["producer"] == "accounts"
    assert event["payload"]["userId"] == body["id"]
    assert event["payload"]["email"] == "ada.lovelace@myumanitoba.ca"
    assert event["payload"]["firstName"] == "Ada"


@pytest.mark.parametrize(
    ("change", "code", "fields"),
    [
        ({"email": "ada@gmail.com"}, "email_not_uofm", ["email"]),
        ({"email": "a b@myumanitoba.ca"}, "invalid_input", ["email"]),
        ({"password": "too short"}, "invalid_input", ["password"]),
        ({"firstName": "   "}, "invalid_input", ["firstName"]),
        ({"lastName": ""}, "invalid_input", ["lastName"]),
    ],
)
async def test_invalid_sign_ups_are_422_naming_the_field(
    api: AsyncClient, session: AsyncSession, change: dict[str, str], code: str, fields: list[str]
) -> None:
    response = await api.post("/auth/signup", json={**SIGNUP, **change})

    assert_problem(response, 422, code, fields)
    assert (await session.execute(select(users))).all() == []
    assert await outbox_events(session) == []


async def test_a_second_account_with_the_same_email_is_409(
    api: AsyncClient, session: AsyncSession
) -> None:
    await api.post("/auth/signup", json=SIGNUP)

    response = await api.post(
        "/auth/signup", json={**SIGNUP, "email": "ADA.LOVELACE@myumanitoba.ca"}
    )

    assert_problem(response, 409, "email_taken", [])
    assert len(await outbox_events(session)) == 1


async def test_sign_up_then_verify_the_email(api: AsyncClient, session: AsyncSession) -> None:
    """User story #2: sign up, click the link in the email, and the account is verified."""
    body = (await api.post("/auth/signup", json=SIGNUP)).json()
    [event] = await outbox_events(session)
    token = event["payload"]["verificationToken"]  # what the email's link carries

    response = await api.post("/auth/verify", json={"token": token})

    assert response.status_code == 204
    session.expire_all()
    row = (await session.execute(select(users).where(users.c.id == body["id"]))).one()
    assert row.email_verified_at is not None
