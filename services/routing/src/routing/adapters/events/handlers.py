"""Handlers for the Trips events that change a trip's accepted pickups (#37).

The detour plans are keyed by the exact points they were worked out for, so a plan for an
old list is never used for a new one. These handlers only free the old plans early.
Forgetting is safe to repeat, so a repeat delivery does no harm.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog.trips import RequestAccepted, RequestCancelled, RequestDeclined, TripCancelled
from events.consumer import StreamConsumer
from routing.application.ports import DetourPlanCache

# Accepting, declining or cancelling a request changes who is in the car; cancelling the
# trip ends it.
PLAN_EVENTS: dict[
    str, type[RequestAccepted | RequestCancelled | RequestDeclined | TripCancelled]
] = {
    RequestAccepted.event_type: RequestAccepted,
    RequestCancelled.event_type: RequestCancelled,
    RequestDeclined.event_type: RequestDeclined,
    TripCancelled.event_type: TripCancelled,
}


def register_handlers(consumer: StreamConsumer, plans: DetourPlanCache) -> None:
    async def forget_plans(event: EventEnvelope, session: AsyncSession) -> None:
        await plans.forget(event.payload_as(PLAN_EVENTS[event.type]).trip_id)

    for payload in PLAN_EVENTS.values():
        consumer.on(payload)(forget_plans)
