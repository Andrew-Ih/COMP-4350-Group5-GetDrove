"""The bell's endpoints (#145) over HTTP, with an in-memory store: the response shape the
frontend reads, and that each user only sees and changes their own notifications."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from common_security.testing import TestAuth
from notifications.adapters.api.dependencies import get_notification_bell
from notifications.application.notification_bell import (
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from notifications.domain.notifications import Notification, NotificationPage, NotificationType
from notifications.infrastructure.main import create_app
from notifications.testing import InMemoryNotificationStore

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


class FakeBell:
    """``NotificationBell`` on the in-memory store instead of PostgreSQL."""

    def __init__(self, store: InMemoryNotificationStore) -> None:
        self.store = store

    async def list(self, *, user_id: UUID, limit: int) -> NotificationPage:
        return await ListNotifications(self.store).execute(user_id=user_id, limit=limit)

    async def mark_read(self, *, user_id: UUID, notification_id: UUID) -> None:
        await MarkNotificationRead(self.store, clock=lambda: NOW).execute(
            user_id=user_id, notification_id=notification_id
        )

    async def mark_all_read(self, *, user_id: UUID) -> None:
        await MarkAllNotificationsRead(self.store, clock=lambda: NOW).execute(user_id=user_id)


@pytest.fixture
def auth() -> TestAuth:
    return TestAuth()


@pytest.fixture
def store() -> InMemoryNotificationStore:
    return InMemoryNotificationStore()


@pytest.fixture
async def client(auth: TestAuth, store: InMemoryNotificationStore) -> AsyncIterator[AsyncClient]:
    app = create_app()
    auth.install(app)
    app.dependency_overrides[get_notification_bell] = lambda: FakeBell(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=auth.headers()
    ) as client:
        yield client


def notification(
    user_id: UUID,
    minutes_ago: int = 0,
    trip_id: UUID | None = None,
    request_id: UUID | None = None,
) -> Notification:
    return Notification(
        user_id=user_id,
        type=NotificationType.REQUEST_ACCEPTED,
        title="Request accepted",
        body="Maya accepted your request for Monday at 7:45 AM.",
        created_at=NOW - timedelta(minutes=minutes_ago),
        trip_id=trip_id,
        request_id=request_id,
    )


async def test_lists_my_notifications_in_the_contract_shape(
    client: AsyncClient, auth: TestAuth, store: InMemoryNotificationStore
) -> None:
    trip_id, request_id = uuid4(), uuid4()
    item = notification(auth.user_id, trip_id=trip_id, request_id=request_id)
    await store.add(item)
    await store.add(notification(uuid4()))  # someone else's

    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(item.id),
                "type": "request_accepted",
                "title": "Request accepted",
                "body": "Maya accepted your request for Monday at 7:45 AM.",
                "tripId": str(trip_id),
                "requestId": str(request_id),
                "createdAt": "2026-11-14T12:00:00Z",
                "readAt": None,
            }
        ],
        "unreadCount": 1,
    }


async def test_a_new_user_has_no_notifications(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.json() == {"items": [], "unreadCount": 0}


async def test_limit_caps_the_list_but_not_the_unread_count(
    client: AsyncClient, auth: TestAuth, store: InMemoryNotificationStore
) -> None:
    for minutes_ago in range(3):
        await store.add(notification(auth.user_id, minutes_ago))

    body = (await client.get("/?limit=2")).json()

    assert len(body["items"]) == 2
    assert body["unreadCount"] == 3


async def test_marking_one_as_read(
    client: AsyncClient, auth: TestAuth, store: InMemoryNotificationStore
) -> None:
    item = notification(auth.user_id)
    await store.add(item)

    response = await client.post(f"/{item.id}/read")

    assert response.status_code == 204
    assert (await client.get("/")).json()["unreadCount"] == 0


async def test_someone_elses_notification_is_404(
    client: AsyncClient, store: InMemoryNotificationStore
) -> None:
    theirs = notification(uuid4())
    await store.add(theirs)

    response = await client.post(f"/{theirs.id}/read")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "notification_not_found"
    assert store.notifications[theirs.id].read_at is None


async def test_marking_all_as_read(
    client: AsyncClient, auth: TestAuth, store: InMemoryNotificationStore
) -> None:
    await store.add(notification(auth.user_id))
    await store.add(notification(auth.user_id, 5))
    theirs = notification(uuid4())
    await store.add(theirs)

    response = await client.post("/read-all")

    assert response.status_code == 204
    assert (await client.get("/")).json()["unreadCount"] == 0
    assert store.notifications[theirs.id].read_at is None
