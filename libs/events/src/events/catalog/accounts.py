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
