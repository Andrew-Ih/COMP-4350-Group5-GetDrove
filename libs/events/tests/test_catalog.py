"""The shared event contracts."""

import secrets
from datetime import UTC, datetime
from uuid import uuid4

from events import EventEnvelope
from events.catalog import (
    ALL_EVENTS,
    RequestAccepted,
    UserRegistered,
    VerificationEmailRequested,
)


def test_user_registered_round_trips_in_camel_case() -> None:
    event = UserRegistered(
        user_id=uuid4(),
        email="ada.lovelace@myumanitoba.ca",
        first_name="Ada",
        verification_token=secrets.token_urlsafe(),
    )
    envelope = EventEnvelope.wrap(event, producer="accounts")

    assert envelope.type == "UserRegistered"
    assert envelope.version == 1
    assert set(envelope.payload) == {"userId", "email", "firstName", "verificationToken"}
    assert EventEnvelope.from_json(envelope.to_json()).payload_as(UserRegistered) == event


def test_verification_email_requested_round_trips_in_camel_case() -> None:
    event = VerificationEmailRequested(
        user_id=uuid4(),
        email="ada.lovelace@myumanitoba.ca",
        first_name="Ada",
        verification_token=secrets.token_urlsafe(),
    )
    envelope = EventEnvelope.wrap(event, producer="accounts")

    assert envelope.type == "VerificationEmailRequested"
    assert envelope.version == 1
    assert set(envelope.payload) == {"userId", "email", "firstName", "verificationToken"}
    assert EventEnvelope.from_json(envelope.to_json()).payload_as(VerificationEmailRequested) == (
        event
    )


def test_every_event_has_a_type_and_version() -> None:
    names = [(event.event_type, event.event_version) for event in ALL_EVENTS]

    assert len(names) == len(set(names))
    assert all(name and version >= 1 for name, version in names)


def test_request_accepted_round_trips_in_camel_case() -> None:
    """One of the Sprint 2 events (#262), with a time and money in it."""
    event = RequestAccepted(
        request_id=uuid4(),
        trip_id=uuid4(),
        rider_id=uuid4(),
        driver_id=uuid4(),
        departure_at=datetime(2026, 11, 16, 13, 10, tzinfo=UTC),
        pickup_label="Osborne St & River Ave",
        amount_cents=420,
        auto_accepted=False,
    )
    envelope = EventEnvelope.wrap(event, producer="trips")

    assert envelope.type == "RequestAccepted"
    assert set(envelope.payload) == {
        "requestId",
        "tripId",
        "riderId",
        "driverId",
        "departureAt",
        "pickupLabel",
        "amountCents",
        "currency",
        "autoAccepted",
    }
    assert envelope.payload["currency"] == "CAD"
    assert EventEnvelope.from_json(envelope.to_json()).payload_as(RequestAccepted) == event


def test_sprint_2_events_are_in_the_catalog() -> None:
    types = {event.event_type for event in ALL_EVENTS}

    assert types >= {
        "SeatRequested",
        "RequestAccepted",
        "RequestDeclined",
        "RequestCancelled",
        "TripCancelled",
        "DriverLateCancellation",
        "DriverApproved",
        "DriverRejected",
        "PaymentHeld",
        "PaymentFailed",
        "PaymentReleased",
    }
