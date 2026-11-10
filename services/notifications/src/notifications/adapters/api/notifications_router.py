"""Notifications API (Sprint 2 contract, #262): the bell. Returns 501 until #145 implements it.

Paths are relative to the gateway prefix /api/notifications. The frontend polls `GET /`
every 3 to 5 seconds while the notification panel is open (ADR 0018).
"""

from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from common_security.dependencies import AuthenticatedUser
from notifications.adapters.api.schemas import NotificationList, Problem

router = APIRouter(tags=["notifications"])

Responses = dict[int | str, dict[str, Any]]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#262).")


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
    limit: Annotated[int, Query(ge=1, le=100, description="How many to return.")] = 30,
) -> NotificationList:
    _not_implemented()


@router.post(
    "/read-all",
    status_code=204,
    summary="Mark all as read",
    responses=UNAUTHORIZED,
)
async def mark_all_read(user: AuthenticatedUser) -> None:
    _not_implemented()


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
async def mark_read(notification_id: UUID, user: AuthenticatedUser) -> None:
    _not_implemented()
