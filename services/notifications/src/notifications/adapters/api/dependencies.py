"""Dependencies for the Notifications API handlers: each request runs its use case in its
own database session."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications.adapters.persistence.notification_store import SQLAlchemyNotificationStore
from notifications.application.notification_bell import (
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from notifications.domain.notifications import NotificationPage


class NotificationBell:
    """The bell's three operations, each in its own transaction."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def list(self, *, user_id: UUID, limit: int) -> NotificationPage:
        async with self.sessions() as session:
            store = SQLAlchemyNotificationStore(session)
            return await ListNotifications(store).execute(user_id=user_id, limit=limit)

    async def mark_read(self, *, user_id: UUID, notification_id: UUID) -> None:
        async with self.sessions() as session, session.begin():
            store = SQLAlchemyNotificationStore(session)
            await MarkNotificationRead(store).execute(
                user_id=user_id, notification_id=notification_id
            )

    async def mark_all_read(self, *, user_id: UUID) -> None:
        async with self.sessions() as session, session.begin():
            store = SQLAlchemyNotificationStore(session)
            await MarkAllNotificationsRead(store).execute(user_id=user_id)


def get_notification_bell(request: Request) -> NotificationBell:
    return NotificationBell(request.app.state.sessions)


NotificationBellService = Annotated[NotificationBell, Depends(get_notification_bell)]
