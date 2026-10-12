"""The port a service's use cases depend on. Adapters implement it (``OutboxPublisher``),
and tests use an in-memory fake."""

from typing import Protocol

from events.envelope import EventPayload


class EventPublisher(Protocol):
    async def publish(self, event: EventPayload) -> None:
        """Records ``event`` to be published once the current transaction commits."""
        ...
