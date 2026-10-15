"""The shared event contracts."""

import secrets
from uuid import uuid4

from events import EventEnvelope
from events.catalog import ALL_EVENTS, UserRegistered, VerificationEmailRequested


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
