"""What each person is told for each event (#146)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from notifications.domain import messages
from notifications.domain.messages import when
from notifications.domain.notifications import NotificationType

# Summer dates: Winnipeg is UTC-5 then under both the old rules and tzdata 2026's (which
# keeps Manitoba on UTC-5 all year from late 2026), so these don't depend on that change.
# 12:45 UTC on Monday 6 July is 7:45 AM in Winnipeg.
DEPARTURE = datetime(2026, 7, 6, 12, 45, tzinfo=UTC)
TRIP, REQUEST, RIDER, DRIVER = uuid4(), uuid4(), uuid4(), uuid4()


@pytest.mark.parametrize(
    ("utc", "shown"),
    [
        (datetime(2026, 7, 6, 12, 45, tzinfo=UTC), "Mon, Jul 6 at 7:45 AM"),
        (datetime(2026, 7, 6, 17, 5, tzinfo=UTC), "Mon, Jul 6 at 12:05 PM"),
        (datetime(2026, 7, 7, 4, 30, tzinfo=UTC), "Mon, Jul 6 at 11:30 PM"),  # still Monday
        (datetime(2026, 7, 13, 5, 0, tzinfo=UTC), "Mon, Jul 13 at 12:00 AM"),  # midnight
    ],
)
def test_times_are_shown_in_winnipeg_time(utc: datetime, shown: str) -> None:
    assert when(utc) == shown


def test_the_driver_hears_about_a_new_request() -> None:
    message = messages.seat_requested(
        driver_id=DRIVER, trip_id=TRIP, request_id=REQUEST, departure_at=DEPARTURE
    )

    assert message.user_id == DRIVER
    assert message.type is NotificationType.SEAT_REQUESTED
    assert "Mon, Jul 6 at 7:45 AM" in message.body
    assert (message.trip_id, message.request_id) == (TRIP, REQUEST)


def test_an_accepted_rider_is_told_the_pickup_point() -> None:
    message = messages.request_accepted(
        rider_id=RIDER,
        trip_id=TRIP,
        request_id=REQUEST,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
    )

    assert message.user_id == RIDER
    assert message.type is NotificationType.REQUEST_ACCEPTED
    assert "Pickup: Pembina Hwy at Chancellor Matheson Rd." in message.body


def test_the_driver_hears_when_auto_accept_seats_a_rider() -> None:
    message = messages.auto_accepted(
        driver_id=DRIVER, trip_id=TRIP, request_id=REQUEST, departure_at=DEPARTURE
    )

    assert message.user_id == DRIVER
    assert message.title == "Rider accepted automatically"
    # The bell sends seat_requested to the driver's trip page (/drive/trips/{id}).
    assert message.type is NotificationType.SEAT_REQUESTED
    assert "Mon, Jul 6 at 7:45 AM" in message.body
    assert message.link_path == messages.MY_TRIPS
    assert (message.trip_id, message.request_id) == (TRIP, REQUEST)


@pytest.mark.parametrize(
    ("was_accepted", "title"), [(False, "Request declined"), (True, "Removed from a trip")]
)
def test_a_declined_rider_is_told_differently_if_they_had_a_seat(
    was_accepted: bool, title: str
) -> None:
    message = messages.request_declined(
        rider_id=RIDER, trip_id=TRIP, request_id=REQUEST, was_accepted=was_accepted
    )

    assert message.user_id == RIDER
    assert message.type is NotificationType.REQUEST_DECLINED
    assert message.title == title
    assert message.link_path == messages.FIND_A_RIDE


@pytest.mark.parametrize(("was_accepted", "freed"), [(False, False), (True, True)])
def test_the_driver_hears_when_a_rider_cancels(was_accepted: bool, freed: bool) -> None:
    message = messages.request_cancelled(
        driver_id=DRIVER, trip_id=TRIP, request_id=REQUEST, was_accepted=was_accepted
    )

    assert message.user_id == DRIVER
    assert message.type is NotificationType.REQUEST_CANCELLED
    assert ("free again" in message.body) is freed


def test_every_rider_hears_once_when_a_trip_is_cancelled() -> None:
    other = uuid4()

    sent = messages.trip_cancelled(
        rider_ids=[RIDER, other, RIDER], trip_id=TRIP, departure_at=DEPARTURE
    )

    assert [message.user_id for message in sent] == [RIDER, other]
    assert all(message.type is NotificationType.TRIP_CANCELLED for message in sent)
    assert "Mon, Jul 6 at 7:45 AM" in sent[0].body


def test_drivers_hear_about_approval_and_why_they_were_rejected() -> None:
    approved = messages.driver_approved(driver_id=DRIVER)
    rejected = messages.driver_rejected(driver_id=DRIVER, reason="The licence photo is blurry.")

    assert approved.type is NotificationType.DRIVER_APPROVED
    assert approved.link_path == messages.POST_A_TRIP
    assert rejected.type is NotificationType.DRIVER_REJECTED
    # A rejected driver can't post trips; they go back to their application.
    assert rejected.link_path == messages.DRIVER_APPLICATION == "/account/driver"
    assert "Reason: The licence photo is blurry. Upload" in rejected.body


@pytest.mark.parametrize(
    ("reason", "problem"),
    [
        ("card_declined", "Your card was declined."),
        ("authentication_required", "Your bank needs you to confirm the payment."),
        ("no_card", "You don't have a card saved."),
        ("other", "We couldn't hold the payment on your card."),
    ],
)
def test_a_rider_is_told_why_their_payment_failed(
    reason: messages.PaymentFailureReason, problem: str
) -> None:
    message = messages.payment_failed(
        rider_id=RIDER, trip_id=TRIP, request_id=REQUEST, reason=reason
    )

    assert message.user_id == RIDER
    assert message.type is NotificationType.PAYMENT_FAILED
    assert message.body.startswith(problem)


def test_the_reminder_names_the_driver_and_the_pickup_point() -> None:
    message = messages.trip_reminder(
        rider_id=RIDER,
        trip_id=TRIP,
        request_id=REQUEST,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy at Chancellor Matheson Rd",
        driver_first_name="Maya",
    )

    assert message.user_id == RIDER
    assert message.type is NotificationType.TRIP_REMINDER
    assert message.title == "Your trip leaves soon"
    assert message.body == (
        "Maya leaves on Mon, Jul 6 at 7:45 AM. "
        "Be at your pickup point: Pembina Hwy at Chancellor Matheson Rd."
    )
    assert (message.trip_id, message.request_id) == (TRIP, REQUEST)


def test_a_reminder_without_the_drivers_name_says_your_driver() -> None:
    message = messages.trip_reminder(
        rider_id=RIDER,
        trip_id=TRIP,
        request_id=REQUEST,
        departure_at=DEPARTURE,
        pickup_label="Pembina Hwy",
        driver_first_name=None,
    )

    assert message.body.startswith("Your driver leaves on")
