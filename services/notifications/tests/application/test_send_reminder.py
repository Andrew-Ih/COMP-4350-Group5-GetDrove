"""SendReminder (#149): a due reminder reaches the rider in the app and by email, naming the
driver, unless the trip has already left."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from notifications.application.notify import Notify
from notifications.application.ports import ContactsUnavailableError
from notifications.application.send_reminder import SendReminder
from notifications.domain.directions import TripDirection
from notifications.domain.notification_email import Contact
from notifications.domain.notifications import NotificationType
from notifications.domain.reminders import ReminderStatus, TripReminder
from notifications.testing import (
    FakeContactDirectory,
    FakeEmailSender,
    InMemoryNotificationStore,
    InMemoryReminderStore,
)

# Summer, so Winnipeg is UTC-5 under both the old and new tz rules: 12:45 UTC is 7:45 AM.
DEPARTURE = datetime(2026, 7, 6, 12, 45, tzinfo=UTC)
DUE = DEPARTURE - timedelta(minutes=30)
RIDER, DRIVER = uuid4(), uuid4()


class World:
    def __init__(self, reminder: TripReminder) -> None:
        self.reminder = reminder
        self.reminders = InMemoryReminderStore(reminder)
        self.notifications = InMemoryNotificationStore()
        self.sender = FakeEmailSender()
        self.contacts = FakeContactDirectory(
            {
                RIDER: Contact("Ada", "ada@myumanitoba.ca"),
                DRIVER: Contact("Maya", "maya@myumanitoba.ca"),
            }
        )

    async def send(self, now: datetime) -> bool:
        notify = Notify(
            store=self.notifications,
            contacts=self.contacts,
            sender=self.sender,
            web_base_url="https://x",
            clock=lambda: now,
        )
        use_case = SendReminder(
            store=self.reminders, notify=notify, contacts=self.contacts, clock=lambda: now
        )
        return await use_case.execute(self.reminder)

    def status(self) -> ReminderStatus:
        return self.reminders.status(self.reminder.request_id)


def reminder(
    driver_id: UUID | None = DRIVER, direction: TripDirection | None = TripDirection.TO_CAMPUS
) -> TripReminder:
    return TripReminder.for_accepted_request(
        rider_id=RIDER,
        trip_id=uuid4(),
        request_id=uuid4(),
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        lead=timedelta(minutes=30),
        driver_id=driver_id,
        direction=direction,
    )


async def test_a_due_reminder_reaches_the_rider_in_the_app_and_by_email() -> None:
    world = World(reminder())

    assert await world.send(DUE) is True

    [note] = world.notifications.notifications.values()
    assert note.user_id == RIDER
    assert note.type is NotificationType.TRIP_REMINDER
    assert note.body == (
        "Maya leaves on Mon, Jul 6 at 7:45 AM. "
        "Be at your pickup point: Pembina Hwy at Chancellor Matheson Rd."
    )
    assert [email.to for email in world.sender.sent] == ["ada@myumanitoba.ca"]
    assert world.status() is ReminderStatus.SENT
    assert world.reminders.handled_at[world.reminder.id] == DUE


async def test_an_overdue_reminder_is_still_sent_before_the_trip_leaves() -> None:
    """E.g. Notifications was down at the due time and came back 20 minutes late."""
    world = World(reminder())

    assert await world.send(DUE + timedelta(minutes=20)) is True

    assert world.status() is ReminderStatus.SENT


@pytest.mark.parametrize("late", [timedelta(0), timedelta(hours=2)])
async def test_once_the_trip_has_left_the_reminder_is_skipped(late: timedelta) -> None:
    world = World(reminder())

    assert await world.send(DEPARTURE + late) is False

    assert world.status() is ReminderStatus.SKIPPED
    assert world.notifications.notifications == {}
    assert world.sender.sent == []


async def test_without_a_known_driver_it_says_your_driver() -> None:
    for driver in (None, uuid4()):  # not stored, or not known to Accounts
        world = World(reminder(driver))

        await world.send(DUE)

        [note] = world.notifications.notifications.values()
        assert note.body.startswith("Your driver leaves on Mon, Jul 6 at 7:45 AM.")


async def test_if_accounts_is_down_it_raises_and_stays_pending() -> None:
    world = World(reminder())
    world.contacts.unavailable = True

    with pytest.raises(ContactsUnavailableError):
        await world.send(DUE)

    assert world.status() is ReminderStatus.PENDING
    assert world.sender.sent == []


async def test_if_the_email_fails_it_raises_and_stays_pending() -> None:
    world = World(reminder())
    world.sender.fail_with = ConnectionError("mail server down")

    with pytest.raises(ConnectionError):
        await world.send(DUE)

    assert world.status() is ReminderStatus.PENDING


async def test_leaving_campus_the_reminder_sends_them_to_campus_not_the_drop_off() -> None:
    """On a trip leaving campus the stored point is where they're dropped off (#355)."""
    world = World(reminder(direction=TripDirection.FROM_CAMPUS))

    await world.send(DUE)

    [note] = world.notifications.notifications.values()
    assert note.body == (
        "Maya leaves campus on Mon, Jul 6 at 7:45 AM. Meet them on campus; "
        "you'll be dropped off at Pembina Hwy at Chancellor Matheson Rd."
    )
    assert "pickup" not in note.body.lower()


async def test_a_reminder_stored_before_direction_was_kept_says_your_stop() -> None:
    world = World(reminder(direction=None))

    await world.send(DUE)

    [note] = world.notifications.notifications.values()
    assert note.body.endswith("Your stop: Pembina Hwy at Chancellor Matheson Rd.")
