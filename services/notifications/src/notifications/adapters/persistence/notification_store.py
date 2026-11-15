"""PostgreSQL implementation of ``NotificationStore`` (#145)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.tables import notifications
from notifications.domain.notifications import Notification, NotificationType


def _notification(row: RowMapping) -> Notification:
    return Notification(
        id=row["id"],
        user_id=row["user_id"],
        type=NotificationType(row["type"]),
        title=row["title"],
        body=row["body"],
        trip_id=row["trip_id"],
        request_id=row["request_id"],
        created_at=row["created_at"],
        read_at=row["read_at"],
    )


class SQLAlchemyNotificationStore:
    """Every query filters on ``user_id``, so nobody reads or changes another user's
    notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, notification: Notification) -> None:
        await self.session.execute(
            insert(notifications).values(
                id=notification.id,
                user_id=notification.user_id,
                type=notification.type.value,
                title=notification.title,
                body=notification.body,
                trip_id=notification.trip_id,
                request_id=notification.request_id,
                created_at=notification.created_at,
                read_at=notification.read_at,
            )
        )

    async def latest(self, user_id: UUID, limit: int) -> list[Notification]:
        result = await self.session.execute(
            select(notifications)
            .where(notifications.c.user_id == user_id)
            .order_by(notifications.c.created_at.desc(), notifications.c.id.desc())
            .limit(limit)
        )
        return [_notification(row) for row in result.mappings()]

    async def unread_count(self, user_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(notifications)
            .where(notifications.c.user_id == user_id, notifications.c.read_at.is_(None))
        )
        return int(count or 0)

    async def mark_read(self, user_id: UUID, notification_id: UUID, at: datetime) -> bool:
        result = await self.session.execute(
            update(notifications)
            .where(notifications.c.id == notification_id, notifications.c.user_id == user_id)
            # One already read keeps the time it was first read.
            .values(read_at=func.coalesce(notifications.c.read_at, at))
            .returning(notifications.c.id)
        )
        return result.first() is not None

    async def mark_all_read(self, user_id: UUID, at: datetime) -> None:
        await self.session.execute(
            update(notifications)
            .where(notifications.c.user_id == user_id, notifications.c.read_at.is_(None))
            .values(read_at=at)
        )
