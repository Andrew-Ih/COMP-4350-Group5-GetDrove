"""Accounts errors. Each ``code`` matches contracts/openapi/accounts.json exactly, because
the frontend checks it. common_web turns them into Problem Details responses."""

from common_web import ConflictError, DomainError, InvalidInputError


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
