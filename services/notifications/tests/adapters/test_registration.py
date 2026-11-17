"""register_event_handlers: one handler per event, running every feature's in order."""

from datetime import timedelta
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import RequestAccepted, SeatRequested
from events.consumer import Handler, StreamConsumer
from notifications.adapters.events.notification_handlers import notification_handlers
from notifications.adapters.events.registration import combine, register_event_handlers
from notifications.adapters.events.reminder_handlers import reminder_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.testing import FakeContactDirectory, FakeEmailSender

NO_SESSION = cast(AsyncSession, None)  # these handlers never touch the database


def consumer() -> StreamConsumer:
    """Only registration is tested, so nothing talks to Redis or the database."""
    return StreamConsumer(
        redis=cast(Any, None),
        session_factory=cast(Any, None),
        group="notifications",
        streams=["events.trips"],
        tables=consumer_tables,
    )


def recording(ran: list[str], name: str) -> Handler:
    async def handler(event: EventEnvelope, session: AsyncSession) -> None:
        ran.append(name)

    return handler


def test_the_services_handlers_all_register_on_one_consumer() -> None:
    """Notifications and reminders both handle RequestAccepted, RequestCancelled,
    RequestDeclined and TripCancelled; this is how main.py registers them."""
    register_event_handlers(
        consumer(),
        notification_handlers(
            contacts=FakeContactDirectory(), sender=FakeEmailSender(), web_base_url="https://x"
        ),
        reminder_handlers(timedelta(minutes=30)),
    )


def test_registering_a_shared_event_twice_directly_would_fail() -> None:
    """Why register_event_handlers exists."""
    shared, ran = consumer(), []
    shared.on(RequestAccepted)(recording(ran, "notify"))

    with pytest.raises(ValueError, match="already registered"):
        shared.on(RequestAccepted)(recording(ran, "remind"))


def test_combine_groups_each_events_handlers() -> None:
    ran: list[str] = []

    combined = combine(
        {RequestAccepted: recording(ran, "notify"), SeatRequested: recording(ran, "notify")},
        {RequestAccepted: recording(ran, "remind")},
    )

    assert {payload: len(handlers) for payload, handlers in combined.items()} == {
        RequestAccepted: 2,
        SeatRequested: 1,
    }


async def test_the_registered_handler_runs_every_features_in_order() -> None:
    ran: list[str] = []
    registered = consumer()
    register_event_handlers(
        registered,
        {RequestAccepted: recording(ran, "notify")},
        {RequestAccepted: recording(ran, "remind")},
    )
    handler = registered._handlers[("RequestAccepted", 1)]  # what the consumer will call

    await handler(EventEnvelope(type="RequestAccepted", producer="trips", payload={}), NO_SESSION)

    assert ran == ["notify", "remind"]
