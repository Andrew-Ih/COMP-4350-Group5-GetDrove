"""FastAPI wiring: who's calling, and role checks."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common_security.config import AuthSettings
from common_security.keys import JwksClient, KeySource
from common_security.user import CurrentUser
from common_security.validator import TokenValidator
from common_web import ForbiddenError, UnauthorizedError, set_user_id

# auto_error=False so a missing header becomes our own 401 Problem Details response.
_bearer = HTTPBearer(
    auto_error=False,
    description="Access token from POST /api/accounts/auth/login "
    "(`Authorization: Bearer <token>`).",
)


def install_security(
    app: FastAPI, *, keys: KeySource | None = None, settings: AuthSettings | None = None
) -> None:
    """Sets up token checking for a service.

    By default the public keys are fetched from Accounts (``AUTH_JWKS_URL``). Accounts
    itself passes its own key with ``keys=StaticKeys(...)``.
    """
    settings = settings or AuthSettings.from_env()
    app.state.token_validator = TokenValidator(keys or JwksClient(settings), settings)


async def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """The logged-in user. Missing or invalid token: 401."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthorizedError("Log in to continue.")
    validator: TokenValidator | None = getattr(request.app.state, "token_validator", None)
    if validator is None:
        raise RuntimeError("install_security(app) wasn't called for this service")
    user = await validator.validate(credentials.credentials)
    set_user_id(str(user.id))  # appears as userId in this request's log lines
    return user


AuthenticatedUser = Annotated[CurrentUser, Depends(current_user)]
"""Use as a parameter type: ``user: AuthenticatedUser``."""


def require_role(role: str) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """A dependency that also requires a role, e.g. ``Depends(require_role("admin"))``.
    Logged in without the role: 403."""

    async def check(user: AuthenticatedUser) -> CurrentUser:
        if not user.has_role(role):
            raise ForbiddenError(f"This needs the {role} role.")
        return user

    return check
