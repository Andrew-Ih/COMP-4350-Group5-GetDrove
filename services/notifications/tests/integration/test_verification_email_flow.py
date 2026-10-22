"""The whole of #93 with nothing faked: the real Notifications app (its startup runs the
consumer), real Redis and PostgreSQL, and a real Mailpit catching the email."""

import asyncio
from typing import Any
from uuid import uuid4

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope, stream_name
from events.catalog import UserRegistered
from events.streams import ENVELOPE_FIELD
from notifications.infrastructure.main import create_app


async def test_a_sign_up_event_becomes_an_email_in_the_inbox(
    session: AsyncSession,
    redis_url: str,
    empty_mailpit: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Configure the app as Docker Compose does, pointing at the throwaway containers.
    monkeypatch.setenv("NOTIFICATIONS_REDIS_URL", redis_url)
    monkeypatch.setenv("NOTIFICATIONS_SMTP_HOST", empty_mailpit.smtp_host)
    monkeypatch.setenv("NOTIFICATIONS_SMTP_PORT", str(empty_mailpit.smtp_port))
    monkeypatch.setenv("NOTIFICATIONS_WEB_BASE_URL", "http://localhost")
    redis = Redis.from_url(redis_url)
    await redis.delete(stream_name("accounts"))
    app = create_app()

    async with app.router.lifespan_context(app):
        # What Accounts' outbox relay puts on the stream when Ada signs up.
        event = UserRegistered(
            user_id=uuid4(),
            email="ada@myumanitoba.ca",
            first_name="Ada",
            verification_token="tok-123",  # noqa: S106 (a test token)
        )
        envelope = EventEnvelope.wrap(event, producer="accounts")
        await redis.xadd(
            stream_name("accounts"), {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type}
        )

        messages: list[dict[str, Any]] = []
        async with httpx.AsyncClient(base_url=empty_mailpit.api, timeout=5) as mailpit:
            for _ in range(100):  # wait up to 10 s for the email to arrive
                messages = (await mailpit.get("/messages")).json()["messages"]
                if messages:
                    break
                await asyncio.sleep(0.1)
            assert len(messages) == 1
            email = (await mailpit.get(f"/message/{messages[0]['ID']}")).json()

    await redis.aclose()
    assert [to["Address"] for to in email["To"]] == ["ada@myumanitoba.ca"]
    assert email["Subject"] == "Verify your GetDrove account"
    assert "Hi Ada," in email["Text"]
    assert "http://localhost/verify?token=tok-123" in email["Text"]
