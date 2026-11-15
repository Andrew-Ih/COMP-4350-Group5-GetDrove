"""PostgreSQL implementation of ``ReminderStore`` (#148)."""

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, RowMapping, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.tables import scheduled_notifications
from notifications.domain.reminders import (
    ReminderStatus,
    ScheduledNotificationType,
    TripReminder,
)


def _reminder(row: RowMapping) -> TripReminder:
    return TripReminder(
        id=row["id"],
        type=ScheduledNotificationType(row["type"]),
        rider_id=row["rider_id"],
        trip_id=row["trip_id"],
        request_id=row["request_id"],
        departure_at=row["departure_at"],
        pickup_label=row["pickup_label"],
        send_at=row["send_at"],
        driver_id=row["driver_id"],
        status=ReminderStatus(row["status"]),
    )


class SQLAlchemyReminderStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, reminder: TripReminder) -> bool:
        table = scheduled_notifications
        result = await self.session.execute(
            insert(table)
            .values(
                id=reminder.id,
                type=reminder.type.value,
                rider_id=reminder.rider_id,
                trip_id=reminder.trip_id,
                request_id=reminder.request_id,
                departure_at=reminder.departure_at,
                pickup_label=reminder.pickup_label,
                send_at=reminder.send_at,
                driver_id=reminder.driver_id,
                status=reminder.status.value,
            )
            .on_conflict_do_nothing(index_elements=[table.c.type, table.c.request_id])
            .returning(table.c.id)
        )
        return result.first() is not None

    async def cancel_for_request(self, request_id: UUID) -> int:
        return await self._cancel(scheduled_notifications.c.request_id == request_id)

    async def cancel_for_trip(self, trip_id: UUID) -> int:
        return await self._cancel(scheduled_notifications.c.trip_id == trip_id)

    async def _cancel(self, which: ColumnElement[bool]) -> int:
        table = scheduled_notifications
        result = await self.session.execute(
            update(table)
            .where(
                which,
                table.c.type == ScheduledNotificationType.TRIP_REMINDER.value,
                table.c.status == ReminderStatus.PENDING.value,
            )
            .values(status=ReminderStatus.CANCELLED.value)
            .returning(table.c.id)
        )
        return len(result.all())

    async def claim_next_due(
        self, now: datetime, skip: Collection[UUID] = ()
    ) -> TripReminder | None:
        table = scheduled_notifications
        query = (
            select(table)
            .where(
                table.c.type == ScheduledNotificationType.TRIP_REMINDER.value,
                table.c.status == ReminderStatus.PENDING.value,
                table.c.send_at <= now,
            )
            .order_by(table.c.send_at, table.c.id)
            .limit(1)
            # Another worker's reminder is passed over, not waited for.
            .with_for_update(skip_locked=True)
        )
        if skip:
            query = query.where(table.c.id.not_in(list(skip)))
        row = (await self.session.execute(query)).mappings().first()
        return _reminder(row) if row is not None else None

    async def mark_sent(self, reminder_id: UUID, at: datetime) -> None:
        await self._finish(reminder_id, ReminderStatus.SENT, at)

    async def mark_skipped(self, reminder_id: UUID, at: datetime) -> None:
        await self._finish(reminder_id, ReminderStatus.SKIPPED, at)

    async def _finish(self, reminder_id: UUID, status: ReminderStatus, at: datetime) -> None:
        table = scheduled_notifications
        await self.session.execute(
            update(table)
            .where(table.c.id == reminder_id, table.c.status == ReminderStatus.PENDING.value)
            .values(status=status.value, handled_at=at)
        )
