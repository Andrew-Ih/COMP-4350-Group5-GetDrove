"""Registers this service's event handlers on its one consumer.

``StreamConsumer`` takes one handler per event type, but some events matter to more than
one feature: ``RequestAccepted`` both notifies people (#146) and schedules a reminder
(#148). Each feature gives a map of event type to handler; for each event, one handler is
registered that runs every feature's, in order, in the event's transaction. So they commit
together with its ``processed_events`` row, or all roll back and the event is retried.
"""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope, EventPayload
from events.consumer import Handler, StreamConsumer

HandlerMap = Mapping[type[EventPayload], Handler]


def combine(*maps: HandlerMap) -> dict[type[EventPayload], list[Handler]]:
    """Every feature's handlers for each event type, in the order the maps were given."""
    combined: dict[type[EventPayload], list[Handler]] = {}
    for handlers in maps:
        for payload, handler in handlers.items():
            combined.setdefault(payload, []).append(handler)
    return combined


def register_event_handlers(consumer: StreamConsumer, *maps: HandlerMap) -> None:
    for payload, handlers in combine(*maps).items():
        consumer.on(payload)(_run_all(handlers))


def _run_all(handlers: list[Handler]) -> Handler:
    if len(handlers) == 1:
        return handlers[0]

    async def run_all(event: EventEnvelope, session: AsyncSession) -> None:
        for handler in handlers:
            await handler(event, session)

    return run_all
