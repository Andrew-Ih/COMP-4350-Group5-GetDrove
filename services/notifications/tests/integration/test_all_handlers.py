"""Every handler on one consumer, registered the way the running service does it: the
notifications (#146) and the reminders (#148) share ``RequestAccepted``, ``RequestCancelled``,
``RequestDeclined`` and ``TripCancelled``, and ``StreamConsumer`` takes one handler per
event, so ``register_event_handlers`` runs both from one. Real Redis and PostgreSQL."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events import EventEnvelope, EventPayload, stream_name
from events.catalog import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from notifications.adapters.events.handlers import register_handlers
from notifications.adapters.events.notification_handlers import notification_handlers
from notifications.adapters.events.registration import register_event_handlers
from notifications.adapters.events.reminder_handlers import reminder_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.adapters.persistence.tables import notifications, scheduled_notifications
from notifications.application.send_verification_email import SendVerificationEmail
from notifications.domain.notification_email import Contact
from notifications.testing import FakeContactDirectory, FakeEmailSender

STREAMS = [stream_name("accounts"), stream_name("trips"), stream_name("payments")]
DEPARTURE = datetime(2026, 11, 16, 13, 45, tzinfo=UTC)
TRIP, DRIVER, RIDER = uuid4(), uuid4(), uuid4()


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url)
    await client.delete(*STREAMS)
    yield client
    await client.aclose()


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def consumer(redis: Redis, session: AsyncSession, sender: FakeEmailSender) -> StreamConsumer:
    """Everything on one consumer, as ``infrastructure/main.py`` registers it."""
    consumer = StreamConsumer(
        redis=redis,
        session_factory=async_sessionmaker(session.bind, expire_on_commit=False),
        group="notifications",
        streams=STREAMS,
        tables=consumer_tables,
        consumer_name=f"notifications-test-{uuid4().hex[:6]}",
        retry_after_ms=0,
    )
    contacts = FakeContactDirectory(
        {
            DRIVER: Contact("Maya", "maya@myumanitoba.ca"),
            RIDER: Contact("Ada", "ada@myumanitoba.ca"),
        }
    )
    register_handlers(consumer, SendVerificationEmail(sender, "https://x"))
    register_event_handlers(
        consumer,
        notification_handlers(contacts=contacts, sender=sender, web_base_url="https://x"),
        reminder_handlers(timedelta(minutes=30)),
    )
    return consumer


async def publish(redis: Redis, event: EventPayload) -> None:
    envelope = EventEnvelope.wrap(event, producer="trips")
    await redis.xadd(
        stream_name("trips"), {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type}
    )


async def handle_new_events(consumer: StreamConsumer) -> None:
    await consumer.ensure_groups()
    await consumer.process_once(block_ms=0)


async def told(session: AsyncSession) -> list[tuple[UUID, str]]:
    rows = await session.execute(
        select(notifications.c.user_id, notifications.c.type).order_by(notifications.c.created_at)
    )
    return [(row.user_id, row.type) for row in rows]


async def reminder_statuses(session: AsyncSession) -> dict[UUID, str]:
    rows = await session.execute(
        select(scheduled_notifications.c.request_id, scheduled_notifications.c.status)
    )
    return {row.request_id: row.status for row in rows}


def accepted(request_id: UUID) -> RequestAccepted:
    return RequestAccepted(
        request_id=request_id,
        trip_id=TRIP,
        rider_id=RIDER,
        driver_id=DRIVER,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        amount_cents=450,
        auto_accepted=False,
    )


async def test_acceptance_notifies_the_rider_and_schedules_their_reminder(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, consumer: StreamConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))

    await handle_new_events(consumer)

    assert await told(session) == [(RIDER, "request_accepted")]
    assert await reminder_statuses(session) == {request: "pending"}
    assert [email.to for email in sender.sent] == ["ada@myumanitoba.ca"]


async def test_cancelling_notifies_the_driver_and_cancels_the_reminder(
    redis: Redis, session: AsyncSession, consumer: StreamConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))
    await publish(
        redis,
        RequestCancelled(
            request_id=request, trip_id=TRIP, rider_id=RIDER, driver_id=DRIVER, was_accepted=True
        ),
    )

    await handle_new_events(consumer)

    assert (await told(session))[-1] == (DRIVER, "request_cancelled")
    assert await reminder_statuses(session) == {request: "cancelled"}


async def test_removing_a_seated_rider_tells_them_and_cancels_the_reminder(
    redis: Redis, session: AsyncSession, consumer: StreamConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))
    await publish(
        redis,
        RequestDeclined(
            request_id=request, trip_id=TRIP, rider_id=RIDER, driver_id=DRIVER, was_accepted=True
        ),
    )

    await handle_new_events(consumer)

    assert (await told(session))[-1] == (RIDER, "request_declined")
    assert await reminder_statuses(session) == {request: "cancelled"}


async def test_a_cancelled_trip_tells_the_riders_and_gets_no_reminders(
    redis: Redis, session: AsyncSession, consumer: StreamConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))
    await publish(
        redis,
        TripCancelled(
            trip_id=TRIP,
            driver_id=DRIVER,
            series_id=None,
            departure_at=DEPARTURE,
            rider_ids=[RIDER],
        ),
    )

    await handle_new_events(consumer)

    assert (await told(session))[-1] == (RIDER, "trip_cancelled")
    assert await reminder_statuses(session) == {request: "cancelled"}


async def test_if_the_notification_fails_the_reminder_rolls_back_too(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, consumer: StreamConsumer
) -> None:
    """Both run in the event's transaction: all of it is saved, or none of it and the event
    is retried."""
    request = uuid4()
    await publish(redis, accepted(request))
    sender.fail_with = ConnectionError("mail server down")

    await handle_new_events(consumer)
    assert await told(session) == []
    assert await reminder_statuses(session) == {}

    sender.fail_with = None
    await handle_new_events(consumer)  # the retry

    assert await told(session) == [(RIDER, "request_accepted")]
    assert await reminder_statuses(session) == {request: "pending"}
