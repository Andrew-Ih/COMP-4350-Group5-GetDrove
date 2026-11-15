"""Existing accepted/held/failed event contracts, with no card references in payloads."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import PaymentFailed, PaymentHeld, RequestAccepted
from events.consumer import StreamConsumer
from events.outbox import OutboxPublisher
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.domain.holds import FailureReason, PaymentHold


class OutboxHoldEvents:
    def __init__(self, publisher: OutboxPublisher) -> None:
        self.publisher = publisher

    async def held(self, hold: PaymentHold) -> None:
        await self.publisher.publish(
            PaymentHeld(
                request_id=hold.request_id,
                trip_id=hold.trip_id,
                rider_id=hold.rider_id,
                amount_cents=hold.amount_cents,
                currency=hold.currency,
            )
        )

    async def failed(self, hold: PaymentHold, reason: FailureReason) -> None:
        await self.publisher.publish(
            PaymentFailed(
                request_id=hold.request_id,
                trip_id=hold.trip_id,
                rider_id=hold.rider_id,
                reason=reason,
            )
        )


async def schedule_accepted(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(RequestAccepted)
    await SQLAlchemyHolds(session).schedule(
        PaymentHold(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            driver_id=data.driver_id,
            amount_cents=data.amount_cents,
            currency=data.currency,
            departure_at=data.departure_at,
            retry_at=datetime.now(UTC),
            correlation_id=event.correlation_id,
        )
    )


def register_hold_handlers(consumer: StreamConsumer) -> None:
    consumer.on(RequestAccepted)(schedule_accepted)
