"""Accounts errors. Each ``code`` matches contracts/openapi/accounts.json exactly, because
the frontend checks it. common_web turns them into Problem Details responses."""

from common_web import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    UnauthorizedError,
)


class EmailNotUofMError(InvalidInputError):
    code = "email_not_uofm"
    title = "Not a UofM email"


class EmailTakenError(ConflictError):
    code = "email_taken"
    title = "Email already registered"


class InvalidVerificationTokenError(DomainError):
    """Unknown, already used, or replaced by a resend (400)."""

    code = "invalid_token"
    title = "Invalid verification link"


class VerificationTokenExpiredError(DomainError):
    """Older than 24 hours; the student can ask for a new link (410)."""

    status = 410
    code = "token_expired"
    title = "Verification link expired"


class InvalidCredentialsError(UnauthorizedError):
    """Wrong email or wrong password: one error for both, so it doesn't reveal which (401)."""

    code = "invalid_credentials"
    title = "Wrong email or password"


class EmailNotVerifiedError(ForbiddenError):
    """Right password, but the email isn't verified yet; the student can resend (403)."""

    code = "email_not_verified"
    title = "Email not verified"


class InvalidRefreshTokenError(UnauthorizedError):
    """The refresh cookie is missing, unknown, expired or already used: log in again (401)."""

    code = "invalid_refresh_token"
    title = "Session expired"


# ---------------------------------------------------------------- drivers (#8)


class DriverAlreadyApprovedError(ConflictError):
    """An approved driver can't replace their documents (409)."""

    code = "driver_already_approved"
    title = "Already approved"


class DriverNotPendingError(ConflictError):
    """Only an application waiting for a decision can be approved or rejected (409)."""

    code = "driver_not_pending"
    title = "Application not pending"


class VehicleMissingError(ConflictError):
    """Approving needs a saved vehicle: riders need it to find their driver (409)."""

    code = "vehicle_missing"
    title = "No vehicle saved"


class DriverNotFoundError(NotFoundError):
    """This user has never applied to drive (404)."""

    code = "driver_not_found"
    title = "No driver application"


class UnsupportedFileTypeError(InvalidInputError):
    """Not a PDF, JPEG or PNG (422)."""

    code = "unsupported_file_type"
    title = "Unsupported file type"


class FileTooLargeError(InvalidInputError):
    """Over 5 MB, or empty (422)."""

    code = "file_too_large"
    title = "File too large"


class DocumentNotFoundError(NotFoundError):
    """No document of this kind has been uploaded (404)."""

    code = "document_not_found"
    title = "No document"
