"""In-app notifications (#145): what a user sees in the bell.

Other parts of the service create them: the trip and request events (#146), trip reminders
(#149). Each belongs to one user, and only that user can read it or mark it as read.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


# What a notification is about; the web app picks its icon from it. (A comment, not a
# docstring: a docstring would become a description in the published OpenAPI contract.)
class NotificationType(StrEnum):
    SEAT_REQUESTED = "seat_requested"
    REQUEST_ACCEPTED = "request_accepted"
    REQUEST_DECLINED = "request_declined"
    REQUEST_CANCELLED = "request_cancelled"
    TRIP_CANCELLED = "trip_cancelled"
    DRIVER_APPROVED = "driver_approved"
    DRIVER_REJECTED = "driver_rejected"
    PAYMENT_FAILED = "payment_failed"
    TRIP_REMINDER = "trip_reminder"


@dataclass(frozen=True)
class Notification:
    user_id: UUID  # who it is for
    type: NotificationType
    title: str
    body: str
    created_at: datetime
    trip_id: UUID | None = None  # the trip it's about, so the bell can link to it
    request_id: UUID | None = None  # the seat request it's about, if any
    read_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


@dataclass(frozen=True)
class NotificationPage:
    """A user's latest notifications, newest first, and how many of all theirs are unread."""

    items: list[Notification]
    unread_count: int
