"""Scheduling and cancelling trip reminders (#148), with an in-memory store."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from notifications.application.trip_reminders import CancelTripReminders, ScheduleTripReminder
from notifications.domain.reminders import ReminderStatus, TripReminder

DEPARTURE = datetime(2026, 11, 16, 7, 45, tzinfo=UTC)
TRIP = uuid4()


class InMemoryReminderStore:
    """``ReminderStore`` in a dict keyed by request, behaving like the PostgreSQL one."""

    def __init__(self) -> None:
        self.reminders: dict[UUID, TripReminder] = {}

    async def add(self, reminder: TripReminder) -> bool:
        if reminder.request_id in self.reminders:
            return False
        self.reminders[reminder.request_id] = reminder
        return True

    async def cancel_for_request(self, request_id: UUID) -> int:
        return self._cancel([r for r in self.reminders.values() if r.request_id == request_id])

    async def cancel_for_trip(self, trip_id: UUID) -> int:
        return self._cancel([r for r in self.reminders.values() if r.trip_id == trip_id])

    def _cancel(self, reminders: list[TripReminder]) -> int:
        pending = [r for r in reminders if r.status is ReminderStatus.PENDING]
        for reminder in pending:
            self.reminders[reminder.request_id] = replace(reminder, status=ReminderStatus.CANCELLED)
        return len(pending)

    def status(self, request_id: UUID) -> ReminderStatus:
        return self.reminders[request_id].status


async def accept(store: InMemoryReminderStore, request_id: UUID, trip_id: UUID = TRIP) -> bool:
    return await ScheduleTripReminder(store).execute(
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
