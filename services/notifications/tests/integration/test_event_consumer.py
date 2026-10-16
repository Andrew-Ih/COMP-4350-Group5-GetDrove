"""Notifications consuming Accounts' events (#93), with real Redis and PostgreSQL and a fake
mail server: one email per event, exactly once, even after a restart."""

from collections.abc import AsyncIterator, Callable
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events import EventEnvelope, EventPayload, stream_name
from events.catalog import UserRegistered, VerificationEmailRequested
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from notifications.adapters.events.handlers import register_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.application.send_verification_email import SendVerificationEmail
from notifications.testing import FakeEmailSender

STREAM = stream_name("accounts")
SITE = "https://getdrove.example"

NewConsumer = Callable[[], StreamConsumer]


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url)
    await client.delete(STREAM)  # a fresh stream (and consumer group) for every test
    yield client
    await client.aclose()


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def new_consumer(redis: Redis, session: AsyncSession, sender: FakeEmailSender) -> NewConsumer:
    """Starts a consumer the way the running service does. Calling it again is like
    restarting the service: a new consumer in the same group, with the same database."""
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)

    def start() -> StreamConsumer:
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group="notifications",
            streams=[STREAM],
            tables=consumer_tables,
            consumer_name=f"notifications-test-{uuid4().hex[:6]}",
            retry_after_ms=0,  # retry a failed event straight away
        )
        register_handlers(consumer, SendVerificationEmail(sender, SITE))
        return consumer

    return start


async def publish(redis: Redis, event: EventPayload) -> EventEnvelope:
    """Puts an event on the stream exactly the way Accounts' outbox relay does."""
    envelope = EventEnvelope.wrap(event, producer="accounts")
    await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type})
    return envelope


async def handle_new_events(consumer: StreamConsumer) -> None:
    """One pass of what the running service does in a loop (``StreamConsumer.run``)."""
    await consumer.ensure_groups()  # the group starts at the beginning of the stream
    await consumer.process_once(block_ms=0)


def user_registered(token: str = "token-1") -> UserRegistered:  # noqa: S107 (a test token)
    return UserRegistered(
        user_id=uuid4(), email="ada@myumanitoba.ca", first_name="Ada", verification_token=token
    )


async def test_signing_up_sends_the_verification_email(
    redis: Redis, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    await publish(redis, user_registered("abc123"))

    await handle_new_events(new_consumer())

    [message] = sender.sent
    assert message.to == "ada@myumanitoba.ca"
    assert f"{SITE}/verify?token=abc123" in message.text


async def test_a_resend_request_sends_the_email_again(
    redis: Redis, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    event = VerificationEmailRequested(
        user_id=uuid4(),
        email="ada@myumanitoba.ca",
        first_name="Ada",
        verification_token="new",  # noqa: S106 (a test token)
    )
    await publish(redis, event)

    await handle_new_events(new_consumer())

    [message] = sender.sent
    assert f"{SITE}/verify?token=new" in message.text


async def test_the_same_event_delivered_twice_sends_one_email(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    envelope = await publish(redis, user_registered())
    # Redis can deliver an event again (e.g. the relay resent it after a crash).
    await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type})

    await handle_new_events(new_consumer())

    assert len(sender.sent) == 1
    recorded = (await session.execute(select(consumer_tables.processed.c.event_id))).scalars()
    assert list(recorded) == [envelope.event_id]


async def test_a_restart_doesnt_send_handled_events_again(
    redis: Redis, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    envelope = await publish(redis, user_registered())
    await handle_new_events(new_consumer())

    # Restart, and the same event turns up again: it's in processed_events, so it's skipped.
    await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type})
    await handle_new_events(new_consumer())

    assert len(sender.sent) == 1


async def test_a_failed_send_is_retried_and_then_sent_once(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    await publish(redis, user_registered())
    consumer = new_consumer()
    sender.fail_with = ConnectionError("mail server down")

    await handle_new_events(consumer)
    assert sender.sent == []
    recorded = (await session.execute(select(consumer_tables.processed))).all()
    assert recorded == []  # not marked handled, so it will be retried

    sender.fail_with = None
    await handle_new_events(consumer)  # the retry

    assert len(sender.sent) == 1


async def test_events_it_doesnt_handle_are_ignored(
    redis: Redis, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    await redis.xadd(
        STREAM,
        {
            ENVELOPE_FIELD: EventEnvelope(
                type="SomethingElse", producer="accounts", payload={}
            ).to_json(),
            "type": "SomethingElse",
        },
    )

    await handle_new_events(new_consumer())

    assert sender.sent == []
