"""PostgreSQL implementation of ``ReminderStore`` (#148)."""

from uuid import UUID

from sqlalchemy import ColumnElement, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.tables import scheduled_notifications
from notifications.domain.reminders import ReminderStatus, TripReminder


class SQLAlchemyReminderStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, reminder: TripReminder) -> bool:
        table = scheduled_notifications
        result = await self.session.execute(
            insert(table)
            .values(
                id=reminder.id,
                rider_id=reminder.rider_id,
                trip_id=reminder.trip_id,
                request_id=reminder.request_id,
                departure_at=reminder.departure_at,
                pickup_label=reminder.pickup_label,
                send_at=reminder.send_at,
                status=reminder.status.value,
            )
            .on_conflict_do_nothing(index_elements=[table.c.request_id])
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
            .where(which, table.c.status == ReminderStatus.PENDING.value)
            .values(status=ReminderStatus.CANCELLED.value)
            .returning(table.c.id)
        )
        return len(result.all())
