"""Notifications API (Sprint 2 contract #262, implemented in #145): the bell.

Paths are relative to the gateway prefix /api/notifications. The frontend polls `GET /`
every 3 to 5 seconds while the notification panel is open (ADR 0018).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query

from common_security.dependencies import AuthenticatedUser
from notifications.adapters.api.dependencies import NotificationBellService
from notifications.adapters.api.schemas import Notification, NotificationList, Problem

router = APIRouter(tags=["notifications"])

Responses = dict[int | str, dict[str, Any]]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


UNAUTHORIZED: Responses = {401: _problem("Missing or invalid access token", "unauthorized")}
INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}


@router.get(
    "/",
    summary="My notifications",
    description="The logged-in user's latest notifications, newest first, and how many are unread.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def list_notifications(
    user: AuthenticatedUser,
    bell: NotificationBellService,
    limit: Annotated[int, Query(ge=1, le=100, description="How many to return.")] = 30,
) -> NotificationList:
    page = await bell.list(user_id=user.id, limit=limit)
    return NotificationList(
        items=[
            Notification(
                id=item.id,
                type=item.type,
                title=item.title,
                body=item.body,
                trip_id=item.trip_id,
                request_id=item.request_id,
                created_at=item.created_at,
                read_at=item.read_at,
            )
            for item in page.items
        ],
        unread_count=page.unread_count,
    )


@router.post(
    "/read-all",
    status_code=204,
    summary="Mark all as read",
    responses=UNAUTHORIZED,
)
async def mark_all_read(user: AuthenticatedUser, bell: NotificationBellService) -> None:
    await bell.mark_all_read(user_id=user.id)


@router.post(
    "/{notification_id}/read",
    status_code=204,
    summary="Mark one as read",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        404: _problem("No notification with this ID for you", "notification_not_found"),
    },
)
async def mark_read(
    notification_id: UUID, user: AuthenticatedUser, bell: NotificationBellService
) -> None:
    await bell.mark_read(user_id=user.id, notification_id=notification_id)
