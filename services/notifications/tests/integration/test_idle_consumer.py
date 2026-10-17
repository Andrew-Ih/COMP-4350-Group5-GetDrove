"""The consumer waiting with nothing to do (#93 follow-up). Found by running the stack:
with redis-py's read timeout equal to the consumer's 5 s wait, idle waits often ended in
"Timeout reading from redis" errors. This waits like the running service does."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events.consumer import StreamConsumer
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.infrastructure.main import CONSUMER_BLOCK_MS, redis_client


async def test_waiting_with_no_events_doesnt_time_out(
    redis_url: str, session: AsyncSession
) -> None:
    redis = redis_client(redis_url)
    stream = f"events.idle-test-{uuid4().hex[:6]}"
    consumer = StreamConsumer(
        redis=redis,
        session_factory=async_sessionmaker(session.bind),
        group="notifications",
        streams=[stream],
        tables=consumer_tables,
        block_ms=CONSUMER_BLOCK_MS,
    )
    await consumer.ensure_groups()

    for _ in range(3):  # before the fix, most of these raised TimeoutError
        assert await consumer.process_once() == 0

    await redis.delete(stream)
    await redis.aclose()
