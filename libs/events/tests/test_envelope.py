"""Unit tests for the envelope: no Docker needed."""

from typing import ClassVar
from uuid import UUID, uuid4

from events import EventEnvelope, EventPayload, stream_name


class TripPosted(EventPayload):
    event_type: ClassVar[str] = "TripPosted"
    event_version: ClassVar[int] = 2

    trip_id: UUID
    seats_total: int


def test_wrap_fills_in_the_metadata() -> None:
    payload = TripPosted(trip_id=uuid4(), seats_total=3)

    envelope = EventEnvelope.wrap(payload, producer="trips", correlation_id="req-1")

    assert envelope.type == "TripPosted"
    assert envelope.version == 2
    assert envelope.producer == "trips"
    assert envelope.correlation_id == "req-1"
    assert envelope.occurred_at.tzinfo is not None
    assert envelope.payload == {"tripId": str(payload.trip_id), "seatsTotal": 3}


def test_json_uses_camel_case_and_round_trips() -> None:
    envelope = EventEnvelope.wrap(TripPosted(trip_id=uuid4(), seats_total=1), producer="trips")

    data = envelope.to_dict()

    assert set(data) == {
        "eventId",
        "type",
        "version",
        "occurredAt",
        "producer",
        "correlationId",
        "payload",
    }
    assert EventEnvelope.from_json(envelope.to_json()) == envelope


def test_each_envelope_gets_its_own_id() -> None:
    payload = TripPosted(trip_id=uuid4(), seats_total=1)

    first = EventEnvelope.wrap(payload, producer="trips")
    second = EventEnvelope.wrap(payload, producer="trips")

    assert first.event_id != second.event_id


def test_payload_as_reads_the_typed_payload() -> None:
    payload = TripPosted(trip_id=uuid4(), seats_total=4)
    envelope = EventEnvelope.from_json(EventEnvelope.wrap(payload, producer="trips").to_json())

    assert envelope.payload_as(TripPosted) == payload


def test_stream_name() -> None:
    assert stream_name("accounts") == "events.accounts"
