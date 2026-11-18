"""Handlers for the Accounts events Trips consumes (#11).

DriverApproved puts the driver on Trips' list of approved drivers, so they can post trips;
DriverRejected takes them off it. ``StreamConsumer`` runs each handler in the transaction
that records the event in ``processed_events``, so a repeat delivery (or a restart) changes
nothing twice. Every other Accounts event (UserRegistered, ...) is ignored.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import DriverApproved, DriverRejected
from events.consumer import StreamConsumer
from trips.adapters.persistence.approved_drivers import SQLAlchemyApprovedDrivers


def register_handlers(consumer: StreamConsumer) -> None:
    @consumer.on(DriverApproved)
    async def driver_approved(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(DriverApproved)
        await SQLAlchemyApprovedDrivers(session).approve(data.user_id, event.occurred_at)

    @consumer.on(DriverRejected)
    async def driver_rejected(event: EventEnvelope, session: AsyncSession) -> None:
        data = event.payload_as(DriverRejected)
        await SQLAlchemyApprovedDrivers(session).remove(data.user_id)
