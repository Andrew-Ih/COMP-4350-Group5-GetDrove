"""Existing accepted/held/failed event contracts, with no card references in payloads."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from events import EventEnvelope
from events.catalog import (
    PaymentFailed,
    PaymentHeld,
    PaymentReleased,
    RequestAccepted,
    RequestCancelled,
    RequestDeclined,
    TripCancelled,
)
from events.consumer import StreamConsumer
from events.outbox import OutboxPublisher
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.domain.holds import FailureReason, PaymentHold, authorization_time


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

    async def released(self, hold: PaymentHold) -> None:
        await self.publisher.publish(
            PaymentReleased(
                request_id=hold.request_id, trip_id=hold.trip_id, rider_id=hold.rider_id
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
    now = datetime.now(UTC)
    # New consumer groups replay history. These are not current payment failures.
    # A zero-cost share needs no authorization either; acknowledge it without a hold.
    if data.departure_at <= now or data.amount_cents == 0:
        return
    authorize_at = authorization_time(event.occurred_at, data.departure_at)
    await SQLAlchemyHolds(session).schedule(
        PaymentHold(
            request_id=data.request_id,
            trip_id=data.trip_id,
            rider_id=data.rider_id,
            driver_id=data.driver_id,
            amount_cents=data.amount_cents,
            currency=data.currency,
            departure_at=data.departure_at,
            authorize_at=authorize_at,
            retry_at=authorize_at,
            correlation_id=event.correlation_id,
        )
    )


def register_hold_handlers(consumer: StreamConsumer) -> None:
    consumer.on(RequestAccepted)(schedule_accepted)
    consumer.on(RequestDeclined)(release_request)
    consumer.on(RequestCancelled)(release_request)
    consumer.on(TripCancelled)(release_trip)


async def release_request(event: EventEnvelope, session: AsyncSession) -> None:
    data: RequestDeclined | RequestCancelled
    if event.type == RequestDeclined.event_type:
        data = event.payload_as(RequestDeclined)
    else:
        data = event.payload_as(RequestCancelled)
    await SQLAlchemyHolds(session).request_release(
        data.request_id,
        data.trip_id,
        data.rider_id,
        data.driver_id,
        event.correlation_id,
        datetime.now(UTC),
    )


async def release_trip(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(TripCancelled)
    await SQLAlchemyHolds(session).release_trip(
        data.trip_id, data.driver_id, event.correlation_id, datetime.now(UTC)
    )
