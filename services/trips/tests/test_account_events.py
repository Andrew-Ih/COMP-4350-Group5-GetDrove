"""Trips' list of approved drivers (#11), kept up to date from Accounts' events, with a
real Redis stream and PostgreSQL: DriverApproved adds the driver, DriverRejected removes
them, a repeat delivery changes nothing twice, and other events are ignored."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from events import EventEnvelope, EventPayload
from events.catalog import DriverApproved, DriverRejected, UserRegistered
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from trips.adapters.account_events import register_handlers
from trips.adapters.persistence.approved_drivers import SQLAlchemyApprovedDrivers
from trips.adapters.persistence.tables import consumer as consumer_tables
from trips.infrastructure.settings import get_settings

pytestmark = pytest.mark.usefixtures("trips_database")


@dataclass
class Stream:
    redis: Redis
    name: str
    engine: AsyncEngine
    consumer: StreamConsumer

    async def deliver(self, payload: EventPayload, *, times: int = 1) -> EventEnvelope:
        envelope = EventEnvelope.wrap(payload, producer="accounts")
        for _ in range(times):  # e.g. the relay crashed after sending, before marking it sent
            await self.redis.xadd(self.name, {ENVELOPE_FIELD: envelope.to_json()})
        await self.consumer.process_once(block_ms=0)
        return envelope

    async def is_approved(self, driver_id: UUID) -> bool:
        async with AsyncSession(self.engine) as session:
            return await SQLAlchemyApprovedDrivers(session).is_approved(driver_id)

    async def count(self, table_name: str, event_id: UUID) -> int:
        table = consumer_tables.processed if table_name == "processed" else consumer_tables.failed
        async with self.engine.connect() as connection:
            found = await connection.scalar(
                select(func.count()).select_from(table).where(table.c.event_id == event_id)
            )
            return found or 0


@pytest.fixture
async def stream(redis_url: str) -> AsyncIterator[Stream]:
    redis = Redis.from_url(redis_url)
    engine = create_async_engine(get_settings().database_url)
    # Each test reads its own stream, so tests never see each other's events.
    name = f"events.accounts.test-{uuid4().hex}"
    consumer = StreamConsumer(
        redis=redis,
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
        group="trips",
        streams=[name],
        tables=consumer_tables,
    )
    register_handlers(consumer)
    await consumer.ensure_groups()
    try:
        yield Stream(redis, name, engine, consumer)
    finally:
        # Drivers are random new IDs, so the rows they leave can't affect other tests.
        await redis.delete(name)
        await redis.aclose()
        await engine.dispose()


async def test_driver_approved_lets_them_post(stream: Stream) -> None:
    driver = uuid4()
    assert not await stream.is_approved(driver)

    await stream.deliver(DriverApproved(user_id=driver))

    assert await stream.is_approved(driver)


async def test_the_same_event_delivered_twice_is_handled_once(stream: Stream) -> None:
    driver = uuid4()

    envelope = await stream.deliver(DriverApproved(user_id=driver), times=2)

    assert await stream.is_approved(driver)
    assert await stream.count("processed", envelope.event_id) == 1
    assert await stream.count("failed", envelope.event_id) == 0


async def test_driver_rejected_takes_them_off_the_list(stream: Stream) -> None:
    driver = uuid4()
    await stream.deliver(DriverApproved(user_id=driver))

    await stream.deliver(DriverRejected(user_id=driver, reason="Expired insurance."))

    assert not await stream.is_approved(driver)


async def test_a_rejection_for_someone_never_approved_is_fine(stream: Stream) -> None:
    driver = uuid4()

    envelope = await stream.deliver(DriverRejected(user_id=driver, reason="Blurry licence."))

    assert not await stream.is_approved(driver)
    assert await stream.count("processed", envelope.event_id) == 1


async def test_approving_again_keeps_them_approved(stream: Stream) -> None:
    driver = uuid4()
    await stream.deliver(DriverApproved(user_id=driver))

    await stream.deliver(DriverApproved(user_id=driver))  # a new event, e.g. re-approved

    assert await stream.is_approved(driver)


async def test_other_accounts_events_are_ignored(stream: Stream) -> None:
    user = uuid4()

    envelope = await stream.deliver(
        UserRegistered(
            user_id=user,
            email="ada@myumanitoba.ca",
            first_name="Ada",
            verification_token="token",  # noqa: S106 (a test value)
        )
    )

    assert not await stream.is_approved(user)
    assert await stream.count("processed", envelope.event_id) == 0
    assert await stream.redis.xpending(stream.name, "trips") == {
        "pending": 0,
        "min": None,
        "max": None,
        "consumers": [],
    }
