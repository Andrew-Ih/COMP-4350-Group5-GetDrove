"""Notify (#146): each message is one in-app notification and one email."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from notifications.application.notify import Notify
from notifications.application.ports import ContactsUnavailableError
from notifications.domain import messages
from notifications.domain.notification_email import Contact
from notifications.testing import FakeContactDirectory, FakeEmailSender, InMemoryNotificationStore

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
DEPARTURE = datetime(2026, 11, 16, 13, 45, tzinfo=UTC)
ADA, ALAN = uuid4(), uuid4()


@pytest.fixture
def store() -> InMemoryNotificationStore:
    return InMemoryNotificationStore()


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def contacts() -> FakeContactDirectory:
    return FakeContactDirectory(
        {
            ADA: Contact("Ada", "ada@myumanitoba.ca"),
            ALAN: Contact("Alan", "alan@myumanitoba.ca"),
        }
    )


def notify(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> Notify:
    return Notify(
        store=store,
        contacts=contacts,
        sender=sender,
        web_base_url="https://getdrove.example",
        clock=lambda: NOW,
    )


async def test_each_person_gets_a_notification_and_an_email(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> None:
    trip = uuid4()
    sent = messages.trip_cancelled(rider_ids=[ADA, ALAN], trip_id=trip, departure_at=DEPARTURE)

    await notify(store, contacts, sender)(sent)

    saved = sorted(store.notifications.values(), key=lambda n: n.user_id == ALAN)
    assert [n.user_id for n in saved] == [ADA, ALAN]
    assert all(n.title == "Trip cancelled" and n.trip_id == trip for n in saved)
    assert all(n.created_at == NOW and n.read_at is None for n in saved)
    assert [email.to for email in sender.sent] == ["ada@myumanitoba.ca", "alan@myumanitoba.ca"]
    assert contacts.asked == [[ADA, ALAN]]  # one lookup for everyone


async def test_someone_accounts_doesnt_know_still_gets_the_in_app_notification(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> None:
    stranger = uuid4()

    await notify(store, contacts, sender)([messages.driver_approved(driver_id=stranger)])

    [saved] = store.notifications.values()
    assert saved.user_id == stranger
    assert sender.sent == []


async def test_if_accounts_is_down_it_raises_so_the_event_is_retried(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> None:
    contacts.unavailable = True

    with pytest.raises(ContactsUnavailableError):
        await notify(store, contacts, sender)([messages.driver_approved(driver_id=ADA)])

    assert store.notifications == {}
    assert sender.sent == []


async def test_a_failed_email_raises_so_the_event_is_retried(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> None:
    sender.fail_with = ConnectionError("mail server down")

    with pytest.raises(ConnectionError):
        await notify(store, contacts, sender)([messages.driver_approved(driver_id=ADA)])


async def test_nothing_to_say_asks_nobody(
    store: InMemoryNotificationStore, contacts: FakeContactDirectory, sender: FakeEmailSender
) -> None:
    await notify(store, contacts, sender)([])

    assert contacts.asked == []
