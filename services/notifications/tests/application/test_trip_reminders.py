"""Scheduling and cancelling trip reminders (#148), with an in-memory store."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from notifications.application.trip_reminders import CancelTripReminders, ScheduleTripReminder
from notifications.domain.reminders import ReminderStatus
from notifications.testing import InMemoryReminderStore

DEPARTURE = datetime(2026, 11, 16, 7, 45, tzinfo=UTC)
TRIP = uuid4()


async def accept(
    store: InMemoryReminderStore,
    request_id: UUID,
    trip_id: UUID = TRIP,
    lead: timedelta = timedelta(minutes=30),
) -> bool:
    return await ScheduleTripReminder(store, lead).execute(
        rider_id=uuid4(),
        trip_id=trip_id,
        request_id=request_id,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
    )


async def test_an_accepted_rider_is_reminded_30_minutes_before_departure() -> None:
    store, request = InMemoryReminderStore(), uuid4()

    assert await accept(store, request) is True

    reminder = store.reminders[request]
    assert reminder.send_at == DEPARTURE - timedelta(minutes=30)
    assert reminder.status is ReminderStatus.PENDING
    assert reminder.trip_id == TRIP
    assert reminder.pickup_label == "Pembina Hwy at Chancellor Matheson Rd"


async def test_the_lead_time_is_configurable() -> None:
    store, request = InMemoryReminderStore(), uuid4()

    await accept(store, request, lead=timedelta(minutes=45))

    assert store.reminders[request].send_at == DEPARTURE - timedelta(minutes=45)


async def test_accepting_the_same_request_twice_keeps_one_reminder() -> None:
    store, request = InMemoryReminderStore(), uuid4()
    await accept(store, request)
    first = store.reminders[request]

    assert await accept(store, request) is False

    assert store.reminders == {request: first}


async def test_cancelling_the_request_cancels_its_reminder() -> None:
    store, mine, other = InMemoryReminderStore(), uuid4(), uuid4()
    await accept(store, mine)
    await accept(store, other)

    assert await CancelTripReminders(store).for_request(mine) == 1

    assert store.status(mine) is ReminderStatus.CANCELLED
    assert store.status(other) is ReminderStatus.PENDING


async def test_cancelling_the_trip_cancels_every_reminder_on_it() -> None:
    store, first, second, elsewhere = InMemoryReminderStore(), uuid4(), uuid4(), uuid4()
    await accept(store, first)
    await accept(store, second)
    await accept(store, elsewhere, trip_id=uuid4())

    assert await CancelTripReminders(store).for_trip(TRIP) == 2

    assert store.status(first) is ReminderStatus.CANCELLED
    assert store.status(second) is ReminderStatus.CANCELLED
    assert store.status(elsewhere) is ReminderStatus.PENDING


async def test_a_sent_reminder_stays_sent() -> None:
    store, request = InMemoryReminderStore(), uuid4()
    await accept(store, request)
    store.reminders[request] = replace(store.reminders[request], status=ReminderStatus.SENT)

    assert await CancelTripReminders(store).for_request(request) == 0

    assert store.status(request) is ReminderStatus.SENT


async def test_cancelling_with_no_reminder_does_nothing() -> None:
    store = InMemoryReminderStore()

    assert await CancelTripReminders(store).for_request(uuid4()) == 0
    assert await CancelTripReminders(store).for_trip(uuid4()) == 0
