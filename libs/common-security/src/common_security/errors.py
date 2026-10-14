"""Token errors. They use common-web's error types, so they come out as Problem Details."""

from common_web import DomainError, UnauthorizedError


class InvalidTokenError(UnauthorizedError):
    code = "invalid_token"
    title = "Invalid access token"


class TokenExpiredError(UnauthorizedError):
    code = "token_expired"
    title = "Access token expired"


class AuthUnavailableError(DomainError):
    """The public key couldn't be fetched from Accounts and none is cached."""

    status = 503
    code = "auth_unavailable"
    title = "Can't check logins right now"
