"""Integration tests: real PostgreSQL and Redis (via testcontainers, so Docker must run).

They follow one event the way it travels in production:
producer transaction -> outbox -> relay -> Redis stream -> consumer group -> handler.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import Column, MetaData, String, Table, Uuid, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from events import EventEnvelope, EventPayload, stream_name
from events.consumer import ConsumerTables, StreamConsumer, consumer_tables
from events.outbox import OutboxPublisher, OutboxRelay, outbox_table
from events.streams import ENVELOPE_FIELD

STREAM = stream_name("accounts")

# A tiny "producer" table, to check that an event and the change behind it commit together,
# plus the tables the library adds to a producer's and a consumer's schema.
metadata = MetaData()
users_table = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", String(200), nullable=False),
)
outbox = outbox_table(metadata)
tables = consumer_tables(metadata)


@dataclass
class Database:
    sessions: async_sessionmaker[AsyncSession]
    users: Table
    outbox: Table
    tables: ConsumerTables


@pytest.fixture
async def db(postgres_url: str) -> AsyncIterator[Database]:
    """Fresh tables for every test."""
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    yield Database(
        sessions=async_sessionmaker(engine, expire_on_commit=False),
        users=users_table,
        outbox=outbox,
        tables=tables,
    )
    await engine.dispose()


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    """An empty Redis for every test."""
    client = Redis.from_url(redis_url, decode_responses=True)
    await client.flushall()
    yield client
    await client.aclose()


class UserRegistered(EventPayload):
    event_type: ClassVar[str] = "UserRegistered"
    event_version: ClassVar[int] = 1

    user_id: UUID
    email: str


# ---------------------------------------------------------------- helpers


async def register_user(db: Database, email: str) -> UUID:
    """What Accounts' signup does: save the user and its event in one transaction."""
    user_id = uuid4()
    async with db.sessions() as session, session.begin():
        await session.execute(insert(db.users).values(id=user_id, email=email))
        await OutboxPublisher(session, db.outbox, producer="accounts").publish(
            UserRegistered(user_id=user_id, email=email)
        )
    return user_id


def make_relay(db: Database, redis: Redis) -> OutboxRelay:
    return OutboxRelay(
        session_factory=db.sessions, redis=redis, table=db.outbox, producer="accounts"
    )


def make_consumer(db: Database, redis: Redis, **options: Any) -> StreamConsumer:
    return StreamConsumer(
        redis=redis,
        session_factory=db.sessions,
        group="notifications",
        streams=[STREAM],
        tables=db.tables,
        **options,
    )


async def count(db: Database, table_name: str) -> int:
    table = {
        "outbox": db.outbox,
        "processed": db.tables.processed,
        "failed": db.tables.failed,
    }[table_name]
    async with db.sessions() as session:
        return int((await session.execute(select(func.count()).select_from(table))).scalar_one())


async def pending(redis: Redis) -> int:
    summary = await redis.xpending(STREAM, "notifications")
    return int(summary["pending"])


# ---------------------------------------------------------------- tests


async def test_committed_event_is_delivered_exactly_once(db: Database, redis: Redis) -> None:
    user_id = await register_user(db, "ada@myumanitoba.ca")

    relay = make_relay(db, redis)
    assert await relay.publish_pending() == 1
    assert await relay.publish_pending() == 0  # already sent
    assert await redis.xlen(STREAM) == 1

    consumer = make_consumer(db, redis)
    received: list[UserRegistered] = []

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        received.append(event.payload_as(UserRegistered))

    # The group is created after the event was sent; starting at the beginning of the
    # stream means it still gets it.
    await consumer.ensure_groups()
    assert await consumer.process_once(block_ms=0) == 1
    assert await consumer.process_once(block_ms=0) == 0

    assert received == [UserRegistered(user_id=user_id, email="ada@myumanitoba.ca")]
    assert await count(db, "processed") == 1
    assert await pending(redis) == 0


async def test_rolled_back_transaction_sends_nothing(db: Database, redis: Redis) -> None:
    class SignupFailedError(Exception):
        pass

    with pytest.raises(SignupFailedError):
        async with db.sessions() as session, session.begin():
            await OutboxPublisher(session, db.outbox, producer="accounts").publish(
                UserRegistered(user_id=uuid4(), email="grace@myumanitoba.ca")
            )
            raise SignupFailedError

    assert await count(db, "outbox") == 0
    assert await make_relay(db, redis).publish_pending() == 0
    assert await redis.xlen(STREAM) == 0


async def test_duplicate_delivery_runs_the_handler_once(db: Database, redis: Redis) -> None:
    envelope = EventEnvelope.wrap(
        UserRegistered(user_id=uuid4(), email="alan@myumanitoba.ca"), producer="accounts"
    )
    # The same event arrives twice, e.g. the relay crashed after sending but before
    # marking the row as sent.
    for _ in range(2):
        await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json()})

    consumer = make_consumer(db, redis)
    calls = 0

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        nonlocal calls
        calls += 1

    await consumer.ensure_groups()
    assert await consumer.process_once(block_ms=0) == 2

    assert calls == 1
    assert await count(db, "processed") == 1
    assert await pending(redis) == 0  # both copies acknowledged


async def test_failed_handler_is_retried(db: Database, redis: Redis) -> None:
    await register_user(db, "katherine@myumanitoba.ca")
    await make_relay(db, redis).publish_pending()

    consumer = make_consumer(db, redis, retry_after_ms=0)
    attempts = 0

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("email server down")

    await consumer.ensure_groups()
    await consumer.process_once(block_ms=0)  # fails, stays pending
    assert await pending(redis) == 1
    assert await count(db, "processed") == 0  # rolled back with the failure

    await consumer.process_once(block_ms=0)  # retried, succeeds

    assert attempts == 2
    assert await count(db, "processed") == 1
    assert await pending(redis) == 0


async def test_handler_that_keeps_failing_is_parked(db: Database, redis: Redis) -> None:
    await register_user(db, "margaret@myumanitoba.ca")
    await make_relay(db, redis).publish_pending()

    consumer = make_consumer(db, redis, retry_after_ms=0, max_attempts=3)

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        raise ValueError("bug in handler")

    await consumer.ensure_groups()
    for _ in range(3):
        await consumer.process_once(block_ms=0)

    assert await pending(redis) == 0  # acknowledged, so it stops blocking the stream
    assert await count(db, "processed") == 0
    async with db.sessions() as session:
        parked = (await session.execute(select(db.tables.failed))).one()
    assert parked.type == "UserRegistered"
    assert parked.attempts == 3
    assert "bug in handler" in parked.error


async def test_message_left_by_a_crashed_consumer_is_picked_up(db: Database, redis: Redis) -> None:
    await register_user(db, "barbara@myumanitoba.ca")
    await make_relay(db, redis).publish_pending()

    consumer = make_consumer(db, redis, retry_after_ms=0, consumer_name="replacement")
    received = 0

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        nonlocal received
        received += 1

    await consumer.ensure_groups()
    # Another instance reads the message, then dies before acknowledging it.
    await redis.xreadgroup("notifications", "crashed", {STREAM: ">"}, count=10)
    assert await pending(redis) == 1

    await consumer.process_once(block_ms=0)

    assert received == 1
    assert await pending(redis) == 0


async def test_events_without_a_handler_are_acknowledged(db: Database, redis: Redis) -> None:
    await register_user(db, "edsger@myumanitoba.ca")
    await make_relay(db, redis).publish_pending()

    consumer = make_consumer(db, redis)  # no handlers registered
    await consumer.ensure_groups()
    assert await consumer.process_once(block_ms=0) == 1

    assert await pending(redis) == 0
    assert await count(db, "processed") == 0


async def test_relay_and_consumer_run_in_the_background(db: Database, redis: Redis) -> None:
    stop = asyncio.Event()
    relay = OutboxRelay(
        session_factory=db.sessions,
        redis=redis,
        table=db.outbox,
        producer="accounts",
        poll_interval=0.05,
    )
    consumer = make_consumer(db, redis, block_ms=50)
    delivered = asyncio.Event()

    @consumer.on(UserRegistered)
    async def handle(event: EventEnvelope, session: AsyncSession) -> None:
        delivered.set()

    tasks = [asyncio.create_task(relay.run(stop)), asyncio.create_task(consumer.run(stop))]
    try:
        await register_user(db, "tim@myumanitoba.ca")
        await asyncio.wait_for(delivered.wait(), timeout=10)
    finally:
        stop.set()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)

    assert await count(db, "processed") == 1
