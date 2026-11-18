"""Request uniqueness and row locks protect holds across events and workers."""

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from payments.adapters.persistence.tables import cancelled_requests, cancelled_trips, payment_holds
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
        authorize_at=row["authorize_at"],
        status=HoldStatus(row["status"]),
        stripe_id=row["stripe_id"],
        release_requested=row["release_requested"],
        card=card,
        first_attempt_at=row["first_attempt_at"],
        retry_at=row["retry_at"],
        correlation_id=row["correlation_id"],
    )


class SQLAlchemyHolds:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _lock_trip(self, trip_id: UUID) -> None:
        # All scheduling/cancellation paths acquire this before any hold row lock.
        # It prevents trip cancellation from missing an acceptance inserted concurrently.
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"payments.trip-holds:{trip_id}"},
        )

    async def schedule(self, hold: PaymentHold) -> None:
        await self._lock_trip(hold.trip_id)
        cancelled = (
            (
                await self.session.execute(
                    select(cancelled_requests).where(
                        cancelled_requests.c.request_id == hold.request_id
                    )
                )
            )
            .mappings()
            .first()
        )
        if cancelled is not None:
            if any(
                cancelled[key] != getattr(hold, key) for key in ("trip_id", "rider_id", "driver_id")
            ):
                raise HoldConflictError("Acceptance conflicts with the cancelled request identity")
            return
        trip = (
            (
                await self.session.execute(
                    select(cancelled_trips).where(cancelled_trips.c.trip_id == hold.trip_id)
                )
            )
            .mappings()
            .first()
        )
        if trip is not None:
            if trip["driver_id"] != hold.driver_id:
                raise HoldConflictError("Acceptance conflicts with the cancelled trip driver")
            return
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
                authorize_at=hold.authorize_at,
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

    async def get(self, request_id: UUID) -> PaymentHold | None:
        result = await self.session.execute(
            select(payment_holds).where(payment_holds.c.request_id == request_id)
        )
        row = result.mappings().first()
        return from_row(row) if row is not None else None

    async def lock(self, request_id: UUID, *, skip_locked: bool = False) -> PaymentHold | None:
        result = await self.session.execute(
            select(payment_holds)
            .where(payment_holds.c.request_id == request_id)
            .with_for_update(skip_locked=skip_locked)
        )
        row = result.mappings().first()
        return from_row(row) if row is not None else None

    async def save(self, hold: PaymentHold) -> None:
        await self.session.execute(
            update(payment_holds)
            .where(payment_holds.c.request_id == hold.request_id)
            .values(
                status=hold.status.value,
                release_requested=hold.release_requested,
                stripe_id=hold.stripe_id,
                customer_id=hold.card.customer_id if hold.card else None,
                payment_method_id=hold.card.payment_method_id if hold.card else None,
                first_attempt_at=hold.first_attempt_at,
                retry_at=hold.retry_at,
            )
        )

    async def due(
        self, now: datetime, limit: int = 20, *, skip: Collection[UUID] = ()
    ) -> list[UUID]:
        result = await self.session.execute(
            select(payment_holds.c.request_id)
            .where(
                or_(
                    payment_holds.c.status == HoldStatus.SCHEDULED.value,
                    payment_holds.c.release_requested.is_(True),
                ),
                payment_holds.c.status != HoldStatus.RELEASED.value,
                payment_holds.c.status != HoldStatus.FAILED.value,
                payment_holds.c.retry_at <= now,
                or_(
                    payment_holds.c.release_requested.is_(True), payment_holds.c.authorize_at <= now
                ),
                payment_holds.c.request_id.not_in(skip),
            )
            .order_by(payment_holds.c.retry_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars())

    async def request_release(
        self,
        request_id: UUID,
        trip_id: UUID,
        rider_id: UUID,
        driver_id: UUID,
        correlation_id: str | None,
        now: datetime,
    ) -> None:
        await self._lock_trip(trip_id)
        await self.session.execute(
            insert(cancelled_requests)
            .values(request_id=request_id, trip_id=trip_id, rider_id=rider_id, driver_id=driver_id)
            .on_conflict_do_nothing()
        )
        recorded = (
            (
                await self.session.execute(
                    select(cancelled_requests).where(cancelled_requests.c.request_id == request_id)
                )
            )
            .mappings()
            .one()
        )
        expected = {"trip_id": trip_id, "rider_id": rider_id, "driver_id": driver_id}
        if any(recorded[key] != value for key, value in expected.items()):
            raise HoldConflictError("Cancellation conflicts with the saved request identity")
        hold = await self.lock(request_id)
        if hold is not None and any(getattr(hold, key) != value for key, value in expected.items()):
            raise HoldConflictError("Cancellation conflicts with the saved hold identity")
        await self._mark_release(payment_holds.c.request_id == request_id, correlation_id, now)

    async def release_trip(
        self, trip_id: UUID, driver_id: UUID, correlation_id: str | None, now: datetime
    ) -> None:
        await self._lock_trip(trip_id)
        await self.session.execute(
            insert(cancelled_trips)
            .values(trip_id=trip_id, driver_id=driver_id)
            .on_conflict_do_nothing()
        )
        recorded = (
            await self.session.execute(
                select(cancelled_trips.c.driver_id).where(cancelled_trips.c.trip_id == trip_id)
            )
        ).scalar_one()
        mismatch = (
            await self.session.execute(
                select(payment_holds.c.request_id).where(
                    payment_holds.c.trip_id == trip_id, payment_holds.c.driver_id != driver_id
                )
            )
        ).first()
        if recorded != driver_id or mismatch:
            raise HoldConflictError("Cancellation conflicts with the saved trip driver")
        await self._mark_release(payment_holds.c.trip_id == trip_id, correlation_id, now)

    async def _mark_release(
        self, condition: ColumnElement[bool], correlation_id: str | None, now: datetime
    ) -> None:
        await self.session.execute(
            update(payment_holds)
            .where(
                condition,
                payment_holds.c.release_requested.is_(False),
                payment_holds.c.status != HoldStatus.RELEASED.value,
                payment_holds.c.status != HoldStatus.FAILED.value,
            )
            .values(release_requested=True, retry_at=now, correlation_id=correlation_id)
        )
