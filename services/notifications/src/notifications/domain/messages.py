"""What each person is told when something happens to their request or trip (#146).

One ``Message`` per person: it becomes an in-app notification and an email. Messages say
"the driver" or "a rider", never another person's name or location; a trip is named by
its departure time, in Winnipeg time.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from notifications.domain.notifications import NotificationType

# Every trip is in Winnipeg, so times are shown in its time zone.
LOCAL_TIME = ZoneInfo("America/Winnipeg")

# Pages of the web app that messages link to.
MY_TRIPS = "/trips"
FIND_A_RIDE = "/ride"
POST_A_TRIP = "/drive/new"
# Where a driver uploads their licence and insurance (#12). A rejected driver can't post
# trips yet, so this is where they go to try again.
DRIVER_APPLICATION = "/account/driver"

PaymentFailureReason = Literal["card_declined", "authentication_required", "no_card", "other"]


@dataclass(frozen=True)
class Message:
    """What one person is told about one event."""

    user_id: UUID
    type: NotificationType
    title: str
    body: str
    link_path: str  # where the email's button goes, e.g. "/trips"
    trip_id: UUID | None = None
    request_id: UUID | None = None


def when(departure_at: datetime) -> str:
    """A departure as people say it: "Mon, Nov 16 at 7:45 AM" (Winnipeg time)."""
    local = departure_at.astimezone(LOCAL_TIME)
    hour = local.hour % 12 or 12
    return f"{local:%a, %b} {local.day} at {hour}:{local:%M %p}"


def seat_requested(
    *, driver_id: UUID, trip_id: UUID, request_id: UUID, departure_at: datetime
) -> Message:
    return Message(
        user_id=driver_id,
        type=NotificationType.SEAT_REQUESTED,
        title="New seat request",
        body=f"A rider asked for a seat on your trip on {when(departure_at)}. "
        "Accept or decline it in My trips.",
        link_path=MY_TRIPS,
        trip_id=trip_id,
        request_id=request_id,
    )


def request_accepted(
    *,
    rider_id: UUID,
    trip_id: UUID,
    request_id: UUID,
    departure_at: datetime,
    pickup_label: str,
) -> Message:
    return Message(
        user_id=rider_id,
        type=NotificationType.REQUEST_ACCEPTED,
        title="Request accepted",
        body=f"You have a seat on the trip on {when(departure_at)}. Pickup: {pickup_label}.",
        link_path=MY_TRIPS,
        trip_id=trip_id,
        request_id=request_id,
    )


def auto_accepted(
    *, driver_id: UUID, trip_id: UUID, request_id: UUID, departure_at: datetime
) -> Message:
    """For the driver when auto-accept seats a rider. That publishes only
    ``RequestAccepted``, never ``SeatRequested``, so this is the driver's only notice."""
    return Message(
        user_id=driver_id,
        type=NotificationType.REQUEST_ACCEPTED,
        title="Rider accepted automatically",
        body=f"A rider was accepted automatically onto your trip on {when(departure_at)}. "
        "See who's coming in My trips.",
        link_path=MY_TRIPS,
        trip_id=trip_id,
        request_id=request_id,
    )


def request_declined(
    *, rider_id: UUID, trip_id: UUID, request_id: UUID, was_accepted: bool
) -> Message:
    if was_accepted:
        title = "Removed from a trip"
        body = (
            "The driver removed you from a trip you had a seat on. You won't be charged for "
            "it. Search for another ride."
        )
    else:
        title = "Request declined"
        body = "The driver declined your seat request. Search for another ride."
    return Message(
        user_id=rider_id,
        type=NotificationType.REQUEST_DECLINED,
        title=title,
        body=body,
        link_path=FIND_A_RIDE,
        trip_id=trip_id,
        request_id=request_id,
    )


def request_cancelled(
    *, driver_id: UUID, trip_id: UUID, request_id: UUID, was_accepted: bool
) -> Message:
    body = (
        "A rider cancelled their seat on your trip. The seat is free again."
        if was_accepted
        else "A rider cancelled their seat request on your trip."
    )
    return Message(
        user_id=driver_id,
        type=NotificationType.REQUEST_CANCELLED,
        title="Request cancelled",
        body=body,
        link_path=MY_TRIPS,
        trip_id=trip_id,
        request_id=request_id,
    )


def trip_cancelled(
    *, rider_ids: Iterable[UUID], trip_id: UUID, departure_at: datetime
) -> list[Message]:
    """One message per rider who had a pending or accepted request."""
    return [
        Message(
            user_id=rider_id,
            type=NotificationType.TRIP_CANCELLED,
            title="Trip cancelled",
            body=f"The driver cancelled the trip on {when(departure_at)}. "
            "You won't be charged for it. Search for another ride.",
            link_path=FIND_A_RIDE,
            trip_id=trip_id,
        )
        for rider_id in dict.fromkeys(rider_ids)
    ]


def driver_approved(*, driver_id: UUID) -> Message:
    return Message(
        user_id=driver_id,
        type=NotificationType.DRIVER_APPROVED,
        title="You're approved to drive",
        body="Your licence and insurance were approved. You can post trips now.",
        link_path=POST_A_TRIP,
    )


def driver_rejected(*, driver_id: UUID, reason: str) -> Message:
    return Message(
        user_id=driver_id,
        type=NotificationType.DRIVER_REJECTED,
        title="Driver documents not approved",
        body=f"Your documents weren't approved. Reason: {reason.strip().rstrip('.')}. "
        "Upload new ones to try again.",
        link_path=DRIVER_APPLICATION,
    )


_PAYMENT_PROBLEMS: dict[PaymentFailureReason, str] = {
    "card_declined": "Your card was declined.",
    "authentication_required": "Your bank needs you to confirm the payment.",
    "no_card": "You don't have a card saved.",
    "other": "We couldn't hold the payment on your card.",
}


def payment_failed(
    *, rider_id: UUID, trip_id: UUID, request_id: UUID, reason: PaymentFailureReason
) -> Message:
    return Message(
        user_id=rider_id,
        type=NotificationType.PAYMENT_FAILED,
        title="Payment failed",
        body=f"{_PAYMENT_PROBLEMS[reason]} Your seat isn't confirmed. "
        "Check your card, then request the seat again.",
        link_path=MY_TRIPS,
        trip_id=trip_id,
        request_id=request_id,
    )
