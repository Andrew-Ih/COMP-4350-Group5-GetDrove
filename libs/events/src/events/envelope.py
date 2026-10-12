"""The envelope every event travels in, and the base class for event payloads."""

import builtins
from datetime import UTC, datetime
from typing import Any, ClassVar, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EventModel(BaseModel):
    """Base for everything sent as an event: camelCase JSON, immutable once created."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        frozen=True,
    )


class EventPayload(EventModel):
    """Base class for an event's data. Each event type is a subclass, for example::

        class UserRegistered(EventPayload):
            event_type: ClassVar[str] = "UserRegistered"
            event_version: ClassVar[int] = 1

            user_id: UUID
            email: str

    Payloads carry IDs and only the data consumers need (never home addresses).
    Adding a field keeps the version; a breaking change is a new version.
    """

    event_type: ClassVar[str]
    event_version: ClassVar[int] = 1


class EventEnvelope(EventModel):
    """Metadata common to every event, wrapped around its payload."""

    event_id: UUID = Field(default_factory=uuid4)
    type: str
    version: int = 1
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str
    correlation_id: str | None = None
    payload: dict[str, Any]

    @classmethod
    def wrap(
        cls, payload: EventPayload, *, producer: str, correlation_id: str | None = None
    ) -> Self:
        """Creates an envelope for ``payload`` with a new event ID and the current time."""
        return cls(
            type=payload.event_type,
            version=payload.event_version,
            producer=producer,
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json", by_alias=True),
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict with camelCase keys."""
        return self.model_dump(mode="json", by_alias=True)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)

    @classmethod
    def from_json(cls, data: str | bytes) -> Self:
        return cls.model_validate_json(data)

    def payload_as[P: EventPayload](self, model: builtins.type[P]) -> P:
        """Reads the payload as a specific event type, validating it."""
        # builtins.type because inside this class, "type" is the event-type field.
        return model.model_validate(self.payload)
