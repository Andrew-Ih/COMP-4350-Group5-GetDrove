"""Events published by the Accounts service."""

from typing import ClassVar
from uuid import UUID

from pydantic import Field

from events.envelope import EventPayload


class UserRegistered(EventPayload):
    """A student signed up. Notifications sends the verification email.

    Published on the ``events.accounts`` stream. Consumers: Notifications.
    """

    event_type: ClassVar[str] = "UserRegistered"
    event_version: ClassVar[int] = 1

    user_id: UUID
    email: str = Field(description="Where to send the verification email.")
    first_name: str = Field(description="For the greeting in the email.")
    verification_token: str = Field(
        description="Goes into the verification link. Valid for 24 hours; a resend replaces it."
    )


class VerificationEmailRequested(EventPayload):
    """A student asked for a new verification link (POST /auth/resend-verification).
    Notifications sends the same email as for ``UserRegistered``; older links have already
    stopped working.

    Not published for unknown or already-verified emails. Published on the
    ``events.accounts`` stream. Consumers: Notifications.
    """

    event_type: ClassVar[str] = "VerificationEmailRequested"
    event_version: ClassVar[int] = 1

    user_id: UUID
    email: str = Field(description="Where to send the verification email.")
    first_name: str = Field(description="For the greeting in the email.")
    verification_token: str = Field(
        description="Goes into the verification link. Valid for 24 hours; a later resend "
        "replaces it."
    )


class DriverApproved(EventPayload):
    """An admin approved a driver (#127). They can post trips straight away, without
    logging in again.

    Published on the ``events.accounts`` stream. Consumers: Trips (its list of approved
    drivers, #11), Notifications (tells the driver).
    """

    event_type: ClassVar[str] = "DriverApproved"
    event_version: ClassVar[int] = 1

    user_id: UUID


class DriverRejected(EventPayload):
    """An admin rejected a driver's documents (#127). They can upload new ones.

    Published on the ``events.accounts`` stream. Consumers: Trips (removes them from its
    list of approved drivers), Notifications (tells the driver why).
    """

    event_type: ClassVar[str] = "DriverRejected"
    event_version: ClassVar[int] = 1

    user_id: UUID
    reason: str = Field(description="Shown to the driver, so they know what to fix.")
