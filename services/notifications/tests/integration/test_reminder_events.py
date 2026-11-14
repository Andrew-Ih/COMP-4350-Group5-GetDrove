"""Trip reminders following Trips' events (#148), with real Redis and PostgreSQL: one
reminder per accepted request, even when an event arrives twice or after a restart, and
cancelled when the request or the trip is."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events import EventEnvelope, EventPayload, stream_name
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from notifications.adapters.events.reminder_handlers import register_reminder_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.adapters.persistence.tables import scheduled_notifications

STREAM = stream_name("trips")
DEPARTURE = datetime(2026, 11, 16, 7, 45, tzinfo=UTC)
TRIP, DRIVER = uuid4(), uuid4()

NewConsumer = Callable[[], StreamConsumer]


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url)
    await client.delete(STREAM)  # a fresh stream (and consumer group) for every test
    yield client
    await client.aclose()


@pytest.fixture
def new_consumer(redis: Redis, session: AsyncSession) -> NewConsumer:
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
            retry_after_ms=0,
        )
        register_reminder_handlers(consumer)
        return consumer

    return start


async def publish(redis: Redis, event: EventPayload) -> EventEnvelope:
    """Puts an event on the stream exactly the way Trips' outbox relay does."""
    envelope = EventEnvelope.wrap(event, producer="trips")
    await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type})
    return envelope


async def handle_new_events(consumer: StreamConsumer) -> None:
    await consumer.ensure_groups()
    await consumer.process_once(block_ms=0)


async def reminders(session: AsyncSession) -> dict[UUID, Any]:
    """Every stored reminder, by request ID."""
    rows = (await session.execute(select(scheduled_notifications))).mappings()
    return {row["request_id"]: row for row in rows}


def accepted(request_id: UUID, rider_id: UUID | None = None) -> RequestAccepted:
    return RequestAccepted(
        request_id=request_id,
        trip_id=TRIP,
        rider_id=rider_id or uuid4(),
        driver_id=DRIVER,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        amount_cents=450,
        auto_accepted=False,
    )


async def test_an_accepted_request_schedules_a_reminder(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    request, rider = uuid4(), uuid4()
    await publish(redis, accepted(request, rider))

    await handle_new_events(new_consumer())

    reminder = (await reminders(session))[request]
    assert reminder["rider_id"] == rider
    assert reminder["trip_id"] == TRIP
    assert reminder["send_at"] == DEPARTURE - timedelta(minutes=30)
    assert reminder["departure_at"] == DEPARTURE
    assert reminder["pickup_label"] == "Pembina Hwy at Chancellor Matheson Rd"
    assert reminder["status"] == "pending"


async def test_the_same_event_twice_schedules_one_reminder(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    request = uuid4()
    envelope = await publish(redis, accepted(request))
    await redis.xadd(STREAM, {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type})

    await handle_new_events(new_consumer())

    assert list(await reminders(session)) == [request]


async def test_a_republished_acceptance_schedules_one_reminder(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    """The same acceptance under a new event ID gets past processed_events; the unique
    request_id still keeps it to one reminder."""
    request = uuid4()
    await publish(redis, accepted(request))
    await handle_new_events(new_consumer())

    await publish(redis, accepted(request))
    await handle_new_events(new_consumer())  # after a restart, too

    assert list(await reminders(session)) == [request]


async def test_the_rider_cancelling_cancels_their_reminder(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    mine, other = uuid4(), uuid4()
    await publish(redis, accepted(mine))
    await publish(redis, accepted(other))
    await publish(
        redis,
        RequestCancelled(
            request_id=mine, trip_id=TRIP, rider_id=uuid4(), driver_id=DRIVER, was_accepted=True
        ),
    )

    await handle_new_events(new_consumer())

    stored = await reminders(session)
    assert stored[mine]["status"] == "cancelled"
    assert stored[other]["status"] == "pending"


async def test_the_driver_removing_a_seated_rider_cancels_their_reminder(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))
    await publish(
        redis,
        RequestDeclined(
            request_id=request,
            trip_id=TRIP,
            rider_id=uuid4(),
            driver_id=DRIVER,
            was_accepted=True,
        ),
    )

    await handle_new_events(new_consumer())

    assert (await reminders(session))[request]["status"] == "cancelled"


async def test_cancelling_the_trip_cancels_every_reminder_on_it(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    first, second = uuid4(), uuid4()
    await publish(redis, accepted(first))
    await publish(redis, accepted(second))
    await publish(
        redis,
        TripCancelled(
            trip_id=TRIP,
            driver_id=DRIVER,
            series_id=None,
            departure_at=DEPARTURE,
            rider_ids=[uuid4(), uuid4()],
        ),
    )

    await handle_new_events(new_consumer())

    assert {row["status"] for row in (await reminders(session)).values()} == {"cancelled"}
