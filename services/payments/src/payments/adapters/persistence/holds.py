"""Request uniqueness and row locks protect holds across events and workers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from payments.adapters.persistence.tables import payment_holds
from payments.application.holds import HoldConflictError
from payments.domain.holds import HoldStatus, PaymentHold, SavedPaymentCard


def from_row(row: RowMapping) -> PaymentHold:
    card = (
        SavedPaymentCard(row["customer_id"], row["payment_method_id"])
        if row["customer_id"] is not None
        else None
    )
    return PaymentHold(
        request_id=row["request_id"],
        trip_id=row["trip_id"],
        rider_id=row["rider_id"],
        driver_id=row["driver_id"],
        amount_cents=row["amount_cents"],
        currency=row["currency"],
        departure_at=row["departure_at"],
        status=HoldStatus(row["status"]),
        stripe_id=row["stripe_id"],
        card=card,
        first_attempt_at=row["first_attempt_at"],
        retry_at=row["retry_at"],
        correlation_id=row["correlation_id"],
    )


class SQLAlchemyHolds:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def schedule(self, hold: PaymentHold) -> None:
        await self.session.execute(
            insert(payment_holds)
            .values(
                request_id=hold.request_id,
                trip_id=hold.trip_id,
                rider_id=hold.rider_id,
                driver_id=hold.driver_id,
                amount_cents=hold.amount_cents,
                currency=hold.currency,
                departure_at=hold.departure_at,
                status=hold.status.value,
                retry_at=hold.retry_at,
                correlation_id=hold.correlation_id,
            )
            .on_conflict_do_nothing(index_elements=[payment_holds.c.request_id])
        )
        existing = await self.lock(hold.request_id)
        if existing is None:
            raise RuntimeError("Scheduled hold was not saved")
        fields = ("trip_id", "rider_id", "driver_id", "amount_cents", "currency", "departure_at")
        if any(getattr(existing, field) != getattr(hold, field) for field in fields):
            raise HoldConflictError("RequestAccepted conflicts with its saved payment hold")

    async def lock(self, request_id: UUID) -> PaymentHold | None:
        result = await self.session.execute(
            select(payment_holds).where(payment_holds.c.request_id == request_id).with_for_update()
        )
        row = result.mappings().first()
        return from_row(row) if row is not None else None

    async def save(self, hold: PaymentHold) -> None:
        await self.session.execute(
            update(payment_holds)
            .where(payment_holds.c.request_id == hold.request_id)
            .values(
                status=hold.status.value,
                stripe_id=hold.stripe_id,
                customer_id=hold.card.customer_id if hold.card else None,
                payment_method_id=hold.card.payment_method_id if hold.card else None,
                first_attempt_at=hold.first_attempt_at,
                retry_at=hold.retry_at,
            )
        )

    async def due(self, now: datetime, limit: int = 20) -> list[UUID]:
        result = await self.session.execute(
            select(payment_holds.c.request_id)
            .where(
                payment_holds.c.status == HoldStatus.SCHEDULED.value,
                payment_holds.c.retry_at <= now,
            )
            .order_by(payment_holds.c.retry_at)
            .limit(limit)
        )
        return list(result.scalars())
