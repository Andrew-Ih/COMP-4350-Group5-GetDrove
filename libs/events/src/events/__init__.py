"""GetDrove events: how services tell each other that something happened (ADR 0005).

- ``EventPayload`` / ``EventEnvelope``: the shape of every event.
- ``EventPublisher``: the port use cases depend on to publish an event.
- ``events.outbox``: transactional outbox (``OutboxPublisher``, ``OutboxRelay``, ``outbox_table``).
- ``events.consumer``: Redis Streams consumer that handles each event once (``StreamConsumer``).

Only the framework-free pieces are imported here, so a service's domain and application
layers can ``from events import EventPayload, EventPublisher`` without pulling in
SQLAlchemy or Redis.
"""

from events.envelope import EventEnvelope, EventModel, EventPayload
from events.ports import EventPublisher
from events.streams import stream_name

__all__ = ["EventEnvelope", "EventModel", "EventPayload", "EventPublisher", "stream_name"]
