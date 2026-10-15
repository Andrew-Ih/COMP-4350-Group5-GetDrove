"""POST /auth/verify and POST /auth/resend-verification (#5), over HTTP against a real
PostgreSQL, checked against contracts/openapi/accounts.json."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import outbox
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.adapters.persistence.verification_token_repository import (
    SqlVerificationTokenRepository,
)
from accounts.domain.email import Email
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken
from accounts.infrastructure.main import create_app
from events import EventEnvelope, stream_name
from events.streams import ENVELOPE_FIELD


async def signed_up(session: AsyncSession, *, verified: bool = False) -> User:
    user = User.register(Email.parse("ada@myumanitoba.ca"), "argon2-hash", "Ada", "Lovelace")
    if verified:
        user.email_verified_at = datetime.now(UTC)
    await SqlUserRepository(session).add(user)
    await session.commit()
    return user


async def link_token(session: AsyncSession, user: User, issued: datetime | None = None) -> str:
    token, link = VerificationToken.issue(user.id, issued or datetime.now(UTC))
    await SqlVerificationTokenRepository(session).add(token)
    await session.commit()
    return link


async def reload(session: AsyncSession, user: User) -> User:
    session.expire_all()
    found = await SqlUserRepository(session).get(user.id)
    assert found is not None
    return found


async def outbox_events(session: AsyncSession) -> list[dict[str, object]]:
    rows = await session.execute(select(outbox.c.envelope).order_by(outbox.c.id))
    return [row.envelope for row in rows]


def assert_problem(response: Response, status: int, code: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code


# ---------------------------------------------------------------- POST /auth/verify


async def test_a_valid_link_verifies_the_email(api: AsyncClient, session: AsyncSession) -> None:
    user = await signed_up(session)
    token = await link_token(session, user)

    response = await api.post("/auth/verify", json={"token": token})

    assert response.status_code == 204
    assert response.content == b""
    assert (await reload(session, user)).email_verified


async def test_a_link_can_only_be_used_once(api: AsyncClient, session: AsyncSession) -> None:
    token = await link_token(session, await signed_up(session))
    await api.post("/auth/verify", json={"token": token})

    response = await api.post("/auth/verify", json={"token": token})

    assert_problem(response, 400, "invalid_token")


async def test_an_unknown_link_is_invalid(api: AsyncClient) -> None:
    response = await api.post("/auth/verify", json={"token": "not-a-real-token"})

    assert_problem(response, 400, "invalid_token")


async def test_an_expired_link_says_so(api: AsyncClient, session: AsyncSession) -> None:
    user = await signed_up(session)
    token = await link_token(session, user, issued=datetime.now(UTC) - timedelta(hours=25))

    response = await api.post("/auth/verify", json={"token": token})

    assert_problem(response, 410, "token_expired")
    assert not (await reload(session, user)).email_verified


async def test_a_missing_token_is_invalid_input(api: AsyncClient) -> None:
    response = await api.post("/auth/verify", json={"token": ""})

    assert_problem(response, 422, "invalid_input")
    assert [e["field"] for e in response.json()["errors"]] == ["token"]


# ---------------------------------------------------------------- POST /auth/resend-verification


async def test_resend_sends_a_new_link_that_replaces_the_old_one(
    api: AsyncClient, session: AsyncSession
) -> None:
    user = await signed_up(session)
    old_token = await link_token(session, user)

    response = await api.post("/auth/resend-verification", json={"email": "Ada@MyUManitoba.ca"})

    assert response.status_code == 202
    [event] = await outbox_events(session)
    assert event["type"] == "VerificationEmailRequested"
    payload = event["payload"]
    assert isinstance(payload, dict)
    assert (payload["userId"], payload["email"], payload["firstName"]) == (
        str(user.id),
        "ada@myumanitoba.ca",
        "Ada",
    )

    old = await api.post("/auth/verify", json={"token": old_token})
    assert_problem(old, 400, "invalid_token")
    new = await api.post("/auth/verify", json={"token": payload["verificationToken"]})
    assert new.status_code == 204


@pytest.mark.parametrize("email", ["nobody@myumanitoba.ca", "ada@gmail.com"])
async def test_resend_answers_202_without_revealing_who_has_an_account(
    api: AsyncClient, session: AsyncSession, email: str
) -> None:
    await signed_up(session)

    response = await api.post("/auth/resend-verification", json={"email": email})

    assert response.status_code == 202
    assert await outbox_events(session) == []


async def test_the_resend_email_request_reaches_redis(
    session: AsyncSession, redis_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the app running (so its outbox relay runs), the event lands on the
    events.accounts stream, where Notifications (#93) will read it."""
    monkeypatch.setenv("ACCOUNTS_REDIS_URL", redis_url)
    user = await signed_up(session)
    app = create_app()
    redis = Redis.from_url(redis_url)
    await redis.delete(stream_name("accounts"))

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/auth/resend-verification", json={"email": "ada@myumanitoba.ca"}
        )
        assert response.status_code == 202
        entries = []
        for _ in range(50):  # the relay checks the outbox every second
            entries = await redis.xrange(stream_name("accounts"))
            if entries:
                break
            await asyncio.sleep(0.1)

    await redis.aclose()
    [(_, fields)] = entries
    envelope = EventEnvelope.from_json(fields[ENVELOPE_FIELD.encode()])
    assert envelope.type == "VerificationEmailRequested"
    assert envelope.producer == "accounts"
    assert envelope.payload["userId"] == str(user.id)


async def test_resend_does_nothing_for_a_verified_account(
    api: AsyncClient, session: AsyncSession
) -> None:
    await signed_up(session, verified=True)

    response = await api.post("/auth/resend-verification", json={"email": "ada@myumanitoba.ca"})

    assert response.status_code == 202
    assert await outbox_events(session) == []
