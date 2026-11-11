"""Request and response models for the Notifications API (Sprint 2 contract, #262).

JSON fields are camelCase; times are ISO 8601 with a timezone.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


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


class Notification(ApiModel):
    id: UUID
    type: NotificationType
    title: str = Field(examples=["Request accepted"])
    body: str = Field(examples=["Maya accepted your request for Monday at 7:45 AM."])
    trip_id: UUID | None = Field(description="The trip it's about, to link to it.")
    request_id: UUID | None = Field(description="The seat request it's about, if any.")
    created_at: AwareDatetime
    read_at: AwareDatetime | None


class NotificationList(ApiModel):
    items: list[Notification] = Field(description="Newest first.")
    unread_count: int = Field(ge=0, description="All unread notifications, not just these.")


# ---------------------------------------------------------------- errors (documentation)


class InvalidFieldOut(ApiModel):
    field: str = Field(examples=["limit"])
    message: str = Field(examples=["Input should be less than or equal to 100"])


class Problem(ApiModel):
    """Every error response (RFC 9457 Problem Details, `application/problem+json`)."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    code: str = Field(description="Stable error name for the frontend to check.")
    request_id: str | None = None
    errors: list[InvalidFieldOut] | None = Field(
        default=None, description="Only on 422: the fields that were invalid."
    )
