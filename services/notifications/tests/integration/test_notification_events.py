"""Request, trip, driver and payment events becoming notifications (#146), with real Redis
and PostgreSQL, a fake Accounts and a fake mail server: one in-app notification and one
email per person, exactly once, even when an event arrives twice or after a restart."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events import EventEnvelope, EventPayload, stream_name
from events.catalog import (
    DriverApproved,
    DriverRejected,
    PaymentFailed,
    RequestAccepted,
    RequestCancelled,
    RequestDeclined,
    SeatRequested,
    TripCancelled,
)
from events.consumer import StreamConsumer
from events.streams import ENVELOPE_FIELD
from notifications.adapters.events.notification_handlers import register_notification_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.adapters.persistence.tables import notifications, trip_members
from notifications.domain.notification_email import Contact
from notifications.testing import FakeContactDirectory, FakeEmailSender

STREAMS = [stream_name("trips"), stream_name("accounts"), stream_name("payments")]
DEPARTURE = datetime(2026, 11, 16, 13, 45, tzinfo=UTC)
TRIP, DRIVER, RIDER = uuid4(), uuid4(), uuid4()

NewConsumer = Callable[[], StreamConsumer]


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(redis_url)
    await client.delete(*STREAMS)  # fresh streams (and consumer groups) for every test
    yield client
    await client.aclose()


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def contacts() -> FakeContactDirectory:
    return FakeContactDirectory(
        {
            DRIVER: Contact("Maya", "maya@myumanitoba.ca"),
            RIDER: Contact("Ada", "ada@myumanitoba.ca"),
        }
    )


@pytest.fixture
def new_consumer(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, contacts: FakeContactDirectory
) -> NewConsumer:
    """Starts a consumer the way the running service does. Calling it again is like
    restarting the service: a new consumer in the same group, with the same database."""
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)

    def start() -> StreamConsumer:
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group="notifications",
            streams=STREAMS,
            tables=consumer_tables,
            consumer_name=f"notifications-test-{uuid4().hex[:6]}",
            retry_after_ms=0,
        )
        register_notification_handlers(
            consumer, contacts=contacts, sender=sender, web_base_url="https://getdrove.example"
        )
        return consumer

    return start


async def publish(redis: Redis, event: EventPayload, producer: str = "trips") -> EventEnvelope:
    """Puts an event on a stream exactly the way the producer's outbox relay does."""
    envelope = EventEnvelope.wrap(event, producer=producer)
    await redis.xadd(
        stream_name(producer), {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type}
    )
    return envelope


async def handle_new_events(consumer: StreamConsumer) -> None:
    await consumer.ensure_groups()
    await consumer.process_once(block_ms=0)


async def told(session: AsyncSession) -> list[tuple[UUID, str]]:
    rows = await session.execute(
        select(notifications.c.user_id, notifications.c.type).order_by(notifications.c.created_at)
    )
    return [(row.user_id, row.type) for row in rows]


async def active_members(session: AsyncSession) -> set[UUID]:
    rows = await session.execute(
        select(trip_members.c.user_id).where(
            trip_members.c.trip_id == TRIP, trip_members.c.active.is_(True)
        )
    )
    return set(rows.scalars())


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


@pytest.mark.parametrize(
    ("event", "producer", "who", "kind"),
    [
        (
            SeatRequested(
                request_id=uuid4(),
                trip_id=TRIP,
                rider_id=RIDER,
                driver_id=DRIVER,
                departure_at=DEPARTURE,
            ),
            "trips",
            DRIVER,
            "seat_requested",
        ),
        (accepted(uuid4()), "trips", RIDER, "request_accepted"),
        (
            RequestDeclined(
                request_id=uuid4(),
                trip_id=TRIP,
                rider_id=RIDER,
                driver_id=DRIVER,
                was_accepted=False,
            ),
            "trips",
            RIDER,
            "request_declined",
        ),
        (
            RequestCancelled(
                request_id=uuid4(),
                trip_id=TRIP,
                rider_id=RIDER,
                driver_id=DRIVER,
                was_accepted=False,
            ),
            "trips",
            DRIVER,
            "request_cancelled",
        ),
        (
            TripCancelled(
                trip_id=TRIP,
                driver_id=DRIVER,
                series_id=None,
                departure_at=DEPARTURE,
                rider_ids=[RIDER],
            ),
            "trips",
            RIDER,
            "trip_cancelled",
        ),
        (DriverApproved(user_id=DRIVER), "accounts", DRIVER, "driver_approved"),
        (
            DriverRejected(user_id=DRIVER, reason="The licence photo is blurry."),
            "accounts",
            DRIVER,
            "driver_rejected",
        ),
        (
            PaymentFailed(request_id=uuid4(), trip_id=TRIP, rider_id=RIDER, reason="card_declined"),
            "payments",
            RIDER,
            "payment_failed",
        ),
    ],
)
async def test_each_event_tells_the_right_person_once_in_app_and_by_email(
    redis: Redis,
    session: AsyncSession,
    sender: FakeEmailSender,
    new_consumer: NewConsumer,
    event: EventPayload,
    producer: str,
    who: UUID,
    kind: str,
) -> None:
    envelope = await publish(redis, event, producer)
    # Delivered twice (e.g. the relay resent it after a crash).
    await redis.xadd(
        stream_name(producer), {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type}
    )

    await handle_new_events(new_consumer())

    assert await told(session) == [(who, kind)]
    email = {DRIVER: "maya@myumanitoba.ca", RIDER: "ada@myumanitoba.ca"}[who]
    assert [message.to for message in sender.sent] == [email]


async def test_a_restart_doesnt_notify_again(
    redis: Redis, session: AsyncSession, sender: FakeEmailSender, new_consumer: NewConsumer
) -> None:
    envelope = await publish(redis, accepted(uuid4()))
    await handle_new_events(new_consumer())

    await redis.xadd(
        stream_name("trips"), {ENVELOPE_FIELD: envelope.to_json(), "type": envelope.type}
    )
    await handle_new_events(new_consumer())

    assert len(await told(session)) == 1
    assert len(sender.sent) == 1


async def test_if_accounts_is_down_the_event_is_retried_and_then_sent_once(
    redis: Redis,
    session: AsyncSession,
    sender: FakeEmailSender,
    contacts: FakeContactDirectory,
    new_consumer: NewConsumer,
) -> None:
    await publish(redis, DriverApproved(user_id=DRIVER), "accounts")
    consumer = new_consumer()
    contacts.unavailable = True

    await handle_new_events(consumer)
    assert await told(session) == []  # rolled back, so it will be retried
    assert sender.sent == []

    contacts.unavailable = False
    await handle_new_events(consumer)  # the retry

    assert await told(session) == [(DRIVER, "driver_approved")]
    assert len(sender.sent) == 1


async def test_trip_members_follow_the_trip(
    redis: Redis, session: AsyncSession, new_consumer: NewConsumer
) -> None:
    request = uuid4()
    await publish(redis, accepted(request))
    await handle_new_events(new_consumer())
    assert await active_members(session) == {DRIVER, RIDER}

    await publish(
        redis,
        RequestCancelled(
            request_id=request, trip_id=TRIP, rider_id=RIDER, driver_id=DRIVER, was_accepted=True
        ),
    )
    await handle_new_events(new_consumer())
    assert await active_members(session) == {DRIVER}

    await publish(
        redis,
        TripCancelled(
            trip_id=TRIP, driver_id=DRIVER, series_id=None, departure_at=DEPARTURE, rider_ids=[]
        ),
    )
    await handle_new_events(new_consumer())
    assert await active_members(session) == set()
