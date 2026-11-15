"""The reminder scheduler (#149) against a real PostgreSQL: due reminders are sent once, in
the app and by email; reminders missed while the service was down are sent on restart if
the trip hasn't left, and skipped if it has; cancelled ones never go out; and two workers
running at once never send the same reminder twice."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications.adapters.persistence.reminder_store import SQLAlchemyReminderStore
from notifications.adapters.persistence.tables import notifications, scheduled_notifications
from notifications.adapters.reminder_scheduler import ReminderScheduler
from notifications.domain.notification_email import Contact
from notifications.domain.reminders import TripReminder
from notifications.testing import FakeContactDirectory, FakeEmailSender

DEPARTURE = datetime(2026, 7, 6, 12, 45, tzinfo=UTC)  # 7:45 AM in Winnipeg
DUE = DEPARTURE - timedelta(minutes=30)
DRIVER = uuid4()
RIDERS = [uuid4() for _ in range(4)]

NewScheduler = Callable[..., ReminderScheduler]


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def contacts() -> FakeContactDirectory:
    known = {DRIVER: Contact("Maya", "maya@myumanitoba.ca")}
    known.update(
        {rider: Contact(f"Rider{i}", f"rider{i}@myumanitoba.ca") for i, rider in enumerate(RIDERS)}
    )
    return FakeContactDirectory(known)


@pytest.fixture
def sessions(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(session.bind, expire_on_commit=False)


@pytest.fixture
def new_scheduler(
    sessions: async_sessionmaker[AsyncSession],
    contacts: FakeContactDirectory,
    sender: FakeEmailSender,
) -> NewScheduler:
    """A scheduler the way the service starts one. A new one is like a restart."""

    def start(now: datetime) -> ReminderScheduler:
        return ReminderScheduler(
            sessions=sessions,
            contacts=contacts,
            sender=sender,
            web_base_url="https://x",
            clock=lambda: now,
        )

    return start


async def store(
    sessions: async_sessionmaker[AsyncSession], rider: UUID, *, cancelled: bool = False
) -> TripReminder:
    """What #148 stores when the rider is accepted (and cancels if the trip is)."""
    reminder = TripReminder.for_accepted_request(
        rider_id=rider,
        trip_id=uuid4(),
        request_id=uuid4(),
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        lead=timedelta(minutes=30),
        driver_id=DRIVER,
    )
    async with sessions() as session, session.begin():
        reminders = SQLAlchemyReminderStore(session)
        await reminders.add(reminder)
        if cancelled:
            await reminders.cancel_for_trip(reminder.trip_id)
    return reminder


async def statuses(session: AsyncSession) -> dict[UUID, str]:
    rows = await session.execute(
        select(scheduled_notifications.c.id, scheduled_notifications.c.status)
    )
    return {row.id: row.status for row in rows}


async def bell(session: AsyncSession) -> list[tuple[UUID, str]]:
    rows = await session.execute(select(notifications.c.user_id, notifications.c.type))
    return [(row.user_id, row.type) for row in rows]


async def test_a_due_reminder_arrives_in_the_app_and_by_email(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    reminder = await store(sessions, RIDERS[0])

    assert await new_scheduler(DUE).run_once() == 1

    assert await bell(session) == [(RIDERS[0], "trip_reminder")]
    [email] = sender.sent
    assert email.to == "rider0@myumanitoba.ca"
    assert "Maya leaves on Mon, Jul 6 at 7:45 AM." in email.text
    assert (await statuses(session))[reminder.id] == "sent"


async def test_a_reminder_isnt_sent_before_it_is_due(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    reminder = await store(sessions, RIDERS[0])

    assert await new_scheduler(DUE - timedelta(seconds=1)).run_once() == 0

    assert sender.sent == []
    assert (await statuses(session))[reminder.id] == "pending"


async def test_after_an_outage_it_is_sent_on_restart_if_the_trip_hasnt_left(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    """Notifications was down at the due time; it comes back 20 minutes later."""
    reminder = await store(sessions, RIDERS[0])

    await new_scheduler(DUE + timedelta(minutes=20)).run_once()

    assert (await statuses(session))[reminder.id] == "sent"
    assert len(sender.sent) == 1


async def test_after_a_long_outage_it_is_skipped_once_the_trip_has_left(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    reminder = await store(sessions, RIDERS[0])

    await new_scheduler(DEPARTURE + timedelta(minutes=5)).run_once()

    assert (await statuses(session))[reminder.id] == "skipped"
    assert sender.sent == []
    assert await bell(session) == []


async def test_a_cancelled_trip_gets_no_reminder(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    reminder = await store(sessions, RIDERS[0], cancelled=True)

    assert await new_scheduler(DUE).run_once() == 0

    assert (await statuses(session))[reminder.id] == "cancelled"
    assert sender.sent == []


async def test_a_restart_doesnt_send_it_again(
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    await store(sessions, RIDERS[0])
    await new_scheduler(DUE).run_once()

    await new_scheduler(DUE + timedelta(minutes=1)).run_once()  # restarted

    assert len(sender.sent) == 1


async def test_two_workers_at_once_never_send_the_same_reminder_twice(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    for rider in RIDERS:
        await store(sessions, rider)

    handled = await asyncio.gather(new_scheduler(DUE).run_once(), new_scheduler(DUE).run_once())

    assert sum(handled) == len(RIDERS)
    assert sorted(email.to for email in sender.sent) == sorted(
        f"rider{i}@myumanitoba.ca" for i in range(len(RIDERS))
    )
    assert set((await statuses(session)).values()) == {"sent"}


async def test_one_that_fails_is_retried_next_pass_and_the_rest_still_go(
    session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    failing = await store(sessions, RIDERS[0])
    working = await store(sessions, RIDERS[1])
    sender.rejects.add("rider0@myumanitoba.ca")

    assert await new_scheduler(DUE).run_once() == 1
    after_first = await statuses(session)
    assert after_first[failing.id] == "pending"  # rolled back, untouched
    assert after_first[working.id] == "sent"
    assert await bell(session) == [(RIDERS[1], "trip_reminder")]  # no half-saved notification

    sender.rejects.clear()
    assert await new_scheduler(DUE + timedelta(seconds=30)).run_once() == 1  # next pass

    assert (await statuses(session))[failing.id] == "sent"


async def test_the_loop_runs_a_pass_and_stops_when_told(
    sessions: async_sessionmaker[AsyncSession],
    sender: FakeEmailSender,
    new_scheduler: NewScheduler,
) -> None:
    await store(sessions, RIDERS[0])
    stop = asyncio.Event()
    scheduler = new_scheduler(DUE)

    runner = asyncio.create_task(scheduler.run(stop, interval_seconds=0.05))
    for _ in range(100):  # up to 5 s for the first pass
        if sender.sent:
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(runner, timeout=2)

    assert len(sender.sent) == 1
