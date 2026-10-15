"""Accounts errors. Each ``code`` matches contracts/openapi/accounts.json exactly, because
the frontend checks it. common_web turns them into Problem Details responses."""

from common_web import ConflictError, InvalidInputError


class EmailNotUofMError(InvalidInputError):
    code = "email_not_uofm"
    title = "Not a UofM email"


class EmailTakenError(ConflictError):
    code = "email_taken"
    title = "Email already registered"
