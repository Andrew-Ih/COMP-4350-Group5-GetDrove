"""Payment events are consumed through the shared contract, not Payments internals."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import PaymentFailed
from events.consumer import StreamConsumer
from trips.adapters.persistence.seat_request_repository import SQLAlchemySeatRequestRepository
from trips.application.payment_failed import HandlePaymentFailed


async def payment_failed(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(PaymentFailed)
    await HandlePaymentFailed(SQLAlchemySeatRequestRepository(session)).execute(
        request_id=data.request_id,
        trip_id=data.trip_id,
        rider_id=data.rider_id,
        now=datetime.now(UTC),
    )


def register_payment_handlers(consumer: StreamConsumer) -> None:
    consumer.on(PaymentFailed)(payment_failed)
