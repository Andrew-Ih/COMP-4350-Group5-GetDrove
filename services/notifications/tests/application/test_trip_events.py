"""TripEventNotifications (#146): the right people are told, and trip_members follows the
trip."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from notifications.application.notify import Notify
from notifications.application.trip_events import TripEventNotifications
from notifications.domain.notification_email import Contact
from notifications.domain.notifications import NotificationType
from notifications.domain.trip_members import TripRole
from notifications.testing import (
    FakeContactDirectory,
    FakeEmailSender,
    InMemoryNotificationStore,
    InMemoryTripMembers,
)

DEPARTURE = datetime(2026, 11, 16, 13, 45, tzinfo=UTC)
TRIP, DRIVER, RIDER = uuid4(), uuid4(), uuid4()


class World:
    def __init__(self) -> None:
        self.store = InMemoryNotificationStore()
        self.sender = FakeEmailSender()
        self.members = InMemoryTripMembers()
        contacts = FakeContactDirectory(
            {
                DRIVER: Contact("Maya", "maya@myumanitoba.ca"),
                RIDER: Contact("Ada", "ada@myumanitoba.ca"),
            }
        )
        notify = Notify(
            store=self.store, contacts=contacts, sender=self.sender, web_base_url="https://x"
        )
        self.events = TripEventNotifications(notify, self.members)

    def told(self) -> list[tuple[UUID, NotificationType]]:
        return [(n.user_id, n.type) for n in self.store.notifications.values()]

    async def active(self) -> list[tuple[UUID, TripRole]]:
        return [(m.user_id, m.role) for m in await self.members.active(TRIP)]


@pytest.fixture
def world() -> World:
    return World()


async def accept(
    world: World, request_id: UUID | None = None, *, auto_accepted: bool = False
) -> None:
    await world.events.request_accepted(
        request_id=request_id or uuid4(),
        trip_id=TRIP,
        rider_id=RIDER,
        driver_id=DRIVER,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        auto_accepted=auto_accepted,
    )


async def test_a_seat_request_tells_the_driver(world: World) -> None:
    await world.events.seat_requested(
        request_id=uuid4(), trip_id=TRIP, driver_id=DRIVER, departure_at=DEPARTURE
    )

    assert world.told() == [(DRIVER, NotificationType.SEAT_REQUESTED)]
    assert [email.to for email in world.sender.sent] == ["maya@myumanitoba.ca"]
    assert await world.active() == [(DRIVER, TripRole.DRIVER)]


async def test_acceptance_tells_the_rider_and_puts_them_on_the_trip(world: World) -> None:
    await accept(world)

    assert world.told() == [(RIDER, NotificationType.REQUEST_ACCEPTED)]
    assert [email.to for email in world.sender.sent] == ["ada@myumanitoba.ca"]
    assert await world.active() == [(DRIVER, TripRole.DRIVER), (RIDER, TripRole.RIDER)]


async def test_an_auto_accepted_rider_is_news_to_the_driver_too(world: World) -> None:
    """Auto-accept publishes only RequestAccepted (no SeatRequested), so the driver is
    told here."""
    await accept(world, auto_accepted=True)

    assert world.told() == [
        (RIDER, NotificationType.REQUEST_ACCEPTED),
        # seat_requested, so the bell opens the driver's trip page, not the rider's view.
        (DRIVER, NotificationType.SEAT_REQUESTED),
    ]
    assert [email.to for email in world.sender.sent] == [
        "ada@myumanitoba.ca",
        "maya@myumanitoba.ca",
    ]
    [driver_note] = [n for n in world.store.notifications.values() if n.user_id == DRIVER]
    assert driver_note.title == "Rider accepted automatically"


async def test_a_decline_tells_the_rider_and_takes_them_off(world: World) -> None:
    request = uuid4()
    await accept(world, request)

    await world.events.request_declined(
        request_id=request, trip_id=TRIP, rider_id=RIDER, was_accepted=True
    )

    assert world.told()[-1] == (RIDER, NotificationType.REQUEST_DECLINED)
    assert await world.active() == [(DRIVER, TripRole.DRIVER)]


async def test_a_cancellation_tells_the_driver_and_takes_the_rider_off(world: World) -> None:
    request = uuid4()
    await accept(world, request)

    await world.events.request_cancelled(
        request_id=request, trip_id=TRIP, rider_id=RIDER, driver_id=DRIVER, was_accepted=True
    )

    assert world.told()[-1] == (DRIVER, NotificationType.REQUEST_CANCELLED)
    assert await world.active() == [(DRIVER, TripRole.DRIVER)]


async def test_a_cancelled_trip_tells_every_rider_including_ones_still_waiting(
    world: World,
) -> None:
    waiting = uuid4()  # requested but not accepted yet, so not a trip member
    await accept(world)

    await world.events.trip_cancelled(
        trip_id=TRIP, rider_ids=[RIDER, waiting], departure_at=DEPARTURE
    )

    assert world.told()[-2:] == [
        (RIDER, NotificationType.TRIP_CANCELLED),
        (waiting, NotificationType.TRIP_CANCELLED),
    ]
    assert await world.active() == []


async def test_drivers_hear_about_approval(world: World) -> None:
    await world.events.driver_approved(driver_id=DRIVER)
    await world.events.driver_rejected(driver_id=DRIVER, reason="Blurry photo")

    assert world.told() == [
        (DRIVER, NotificationType.DRIVER_APPROVED),
        (DRIVER, NotificationType.DRIVER_REJECTED),
    ]


async def test_a_failed_payment_tells_the_rider_and_frees_their_place(world: World) -> None:
    request = uuid4()
    await accept(world, request)

    await world.events.payment_failed(
        request_id=request, trip_id=TRIP, rider_id=RIDER, reason="card_declined"
    )

    assert world.told()[-1] == (RIDER, NotificationType.PAYMENT_FAILED)
    assert await world.active() == [(DRIVER, TripRole.DRIVER)]
