"""Use cases for logging in (#6): POST /auth/login and GET /me."""

from dataclasses import dataclass
from uuid import UUID

from accounts.application.ports import AccessTokenIssuer, Clock, PasswordHasher, UnitOfWork
from accounts.domain.email import Email
from accounts.domain.errors import EmailNotVerifiedError, InvalidCredentialsError
from accounts.domain.refresh_token import RefreshToken
from accounts.domain.user import User
from common_web import InvalidInputError, UnauthorizedError


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int  # seconds
    refresh_token: str  # goes in the HttpOnly cookie, never in the response body


class LogIn:
    """POST /auth/login: 200 with tokens, 401 invalid_credentials, or 403 email_not_verified.

    The order matters. An unknown email and a wrong password give the same 401, and take
    the same time. "Not verified" is only said after the password is right, so neither
    response reveals whether an account exists.
    """

    def __init__(
        self, uow: UnitOfWork, hasher: PasswordHasher, tokens: AccessTokenIssuer, clock: Clock
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock

    async def __call__(self, email: str, password: str) -> LoginResult:
        try:
            parsed: Email | None = Email.parse(email)
        except InvalidInputError:
            parsed = None  # can't have an account, but answer like any wrong login

        async with self._uow as uow:
            user = await uow.users.get_by_email(parsed) if parsed else None
            if user is None:
                self._hasher.verify_dummy(password)
                raise InvalidCredentialsError("Wrong email or password.")
            if not self._hasher.verify(user.password_hash, password):
                raise InvalidCredentialsError("Wrong email or password.")
            if not user.email_verified:
                raise EmailNotVerifiedError("Verify your email before logging in.")

            now = self._clock.now()
            refresh, cookie_token = RefreshToken.issue(user.id, now)
            await uow.refresh_tokens.add(refresh)
            await uow.commit()

        return LoginResult(
            access_token=self._tokens.issue(user, now),
            expires_in=int(self._tokens.lifetime.total_seconds()),
            refresh_token=cookie_token,
        )


class GetMe:
    """GET /me: the logged-in user. 401 if their account no longer exists."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> User:
        async with self._uow as uow:
            user = await uow.users.get(user_id)
        if user is None:
            raise UnauthorizedError("Log in to continue.")
        return user
