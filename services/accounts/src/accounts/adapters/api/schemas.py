"""Request and response models for the Accounts API (contracts: #108, #262).

JSON fields are camelCase. Passwords and tokens are never returned or logged.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


EMAIL_FIELD = Field(
    min_length=3,
    max_length=254,
    description="UofM student email (must end in @myumanitoba.ca).",
    examples=["ada.lovelace@myumanitoba.ca"],
)


# ---------------------------------------------------------------- sign up and verify


class SignupRequest(ApiModel):
    email: str = EMAIL_FIELD
    password: str = Field(
        min_length=10,
        max_length=128,
        description="At least 10 characters.",
        examples=["correct horse battery"],
    )
    first_name: str = Field(min_length=1, max_length=50, examples=["Ada"])
    last_name: str = Field(min_length=1, max_length=50, examples=["Lovelace"])


class SignupResponse(ApiModel):
    id: UUID
    email: str
    email_verified: bool = Field(
        default=False, description="Always false: a verification email has been sent."
    )


class VerifyEmailRequest(ApiModel):
    token: str = Field(
        min_length=1, max_length=200, description="The token from the verification link."
    )


class ResendVerificationRequest(ApiModel):
    email: str = EMAIL_FIELD


# ---------------------------------------------------------------- log in


class LoginRequest(ApiModel):
    email: str = EMAIL_FIELD
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ApiModel):
    """An access token. Send it as `Authorization: Bearer <accessToken>`.

    The refresh token is never in the body: it's set as an HttpOnly cookie.
    """

    access_token: str = Field(examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6ImsxIn0..."])
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 (a token type, not a secret)
    expires_in: int = Field(
        description="Seconds until the access token expires (900).", examples=[900]
    )


# ---------------------------------------------------------------- the current user


class User(ApiModel):
    id: UUID
    email: str = Field(examples=["ada.lovelace@myumanitoba.ca"])
    first_name: str = Field(examples=["Ada"])
    last_name: str = Field(examples=["Lovelace"])
    email_verified: bool
    roles: list[Literal["user", "admin"]] = Field(
        description="Every account is a `user` (rider and driver). `admin` can approve "
        "drivers (Sprint 2).",
        examples=[["user"]],
    )


# ---------------------------------------------------------------- drivers (#8)


class DriverStatus(StrEnum):
    NONE = "none"  # never applied
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentKind(StrEnum):
    LICENCE = "licence"
    INSURANCE = "insurance"


class Vehicle(ApiModel):
    make: str = Field(min_length=1, max_length=30, examples=["Honda"])
    model: str = Field(min_length=1, max_length=30, examples=["Civic"])
    colour: str = Field(min_length=1, max_length=30, examples=["Blue"])
    plate: str = Field(
        pattern=r"^[A-Za-z0-9]{2,8}$",
        description="2 to 8 letters and digits, no spaces. Stored and returned in uppercase. "
        "Only shown to the driver, admins, and riders accepted on their trips.",
        examples=["ABC123"],
    )


class DocumentsUploaded(ApiModel):
    licence: bool
    insurance: bool


class DriverProfile(ApiModel):
    """The logged-in user's own driver status."""

    status: DriverStatus
    rejection_reason: str | None = Field(description="Set when `status` is `rejected`.")
    documents: DocumentsUploaded
    vehicle: Vehicle | None
    submitted_at: AwareDatetime | None = Field(description="When documents were last uploaded.")
    reviewed_at: AwareDatetime | None = Field(description="When an admin last decided.")


class AdminDriver(ApiModel):
    """A driver application, as an admin sees it."""

    user_id: UUID
    first_name: str = Field(examples=["Ada"])
    last_name: str = Field(examples=["Lovelace"])
    email: str = Field(examples=["ada.lovelace@myumanitoba.ca"])
    status: DriverStatus
    vehicle: Vehicle | None
    documents: DocumentsUploaded
    submitted_at: AwareDatetime | None
    reviewed_at: AwareDatetime | None
    rejection_reason: str | None


class RejectDriverRequest(ApiModel):
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="Shown to the driver, so they know what to fix.",
        examples=["The insurance document has expired."],
    )


# ---------------------------------------------------------------- profiles (#143)


class PublicVehicle(ApiModel):
    """A vehicle without its plate."""

    make: str = Field(examples=["Honda"])
    model: str = Field(examples=["Civic"])
    colour: str = Field(examples=["Blue"])


class PublicProfile(ApiModel):
    """What any logged-in student can see about another."""

    id: UUID
    first_name: str = Field(examples=["Ada"])
    rating: float | None = Field(
        ge=1, le=5, description="Average rating; null if they have no ratings yet."
    )
    rating_count: int = Field(ge=0)
    trip_count: int = Field(ge=0, description="Completed trips, as a driver or rider.")
    is_driver: bool = Field(description="An approved driver.")
    vehicle: PublicVehicle | None = Field(description="Approved drivers only.")


class InternalUser(ApiModel):
    """For Trips: names, ratings, no-shows and drivers' vehicles. No email."""

    id: UUID
    first_name: str
    rating: float | None = Field(ge=1, le=5)
    rating_count: int = Field(ge=0)
    trip_count: int = Field(ge=0)
    no_show_count: int = Field(ge=0)
    vehicle: Vehicle | None = Field(
        description="Approved drivers only, with the plate: Trips shows it to the riders "
        "accepted on their trips."
    )


class InternalUsers(ApiModel):
    users: list[InternalUser] = Field(description="Unknown IDs are left out.")


class InternalContact(ApiModel):
    """For Notifications only: where to send emails."""

    id: UUID
    first_name: str
    email: str


class InternalContacts(ApiModel):
    contacts: list[InternalContact] = Field(description="Unknown IDs are left out.")


# ---------------------------------------------------------------- JWKS


class Jwk(BaseModel):
    """One public signing key (RFC 7517). Field names follow the standard, not camelCase."""

    kty: Literal["RSA"] = "RSA"
    kid: str = Field(
        description="Key ID; matches the `kid` in each token's header.", examples=["2026-10-k1"]
    )
    use: Literal["sig"] = "sig"
    alg: Literal["RS256"] = "RS256"
    n: str = Field(description="RSA modulus, base64url.")
    e: str = Field(description="RSA exponent, base64url.", examples=["AQAB"])


class JwkSet(BaseModel):
    keys: list[Jwk]


# ---------------------------------------------------------------- errors (documentation)


class InvalidFieldOut(ApiModel):
    field: str = Field(examples=["password"])
    message: str = Field(examples=["String should have at least 10 characters"])


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
        default=None, description="Only on 422: the invalid fields."
    )
