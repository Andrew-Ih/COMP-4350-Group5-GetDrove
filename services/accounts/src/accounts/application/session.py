"""Use cases for staying logged in (#90): POST /auth/refresh and POST /auth/logout."""

from accounts.application.login import LoginResult
from accounts.application.ports import AccessTokenIssuer, Clock, UnitOfWork
from accounts.domain.errors import InvalidRefreshTokenError
from accounts.domain.verification import hash_token


class RefreshSession:
    """POST /auth/refresh: swaps the refresh cookie for a new one and issues a new access
    token. 401 invalid_refresh_token for a missing, unknown, expired or used cookie.

    Reuse detection: a cookie that was already swapped (it has a replacement) should never
    come back, so if it does, a copy is being used, by the student or by a thief. All of
    that student's sessions are ended, and they log in again.
    """

    def __init__(self, uow: UnitOfWork, tokens: AccessTokenIssuer, clock: Clock) -> None:
        self._uow = uow
        self._tokens = tokens
        self._clock = clock

    async def __call__(self, cookie_token: str | None) -> LoginResult:
        if not cookie_token:
            raise InvalidRefreshTokenError("Log in again.")
        now = self._clock.now()

        async with self._uow as uow:
            saved = await uow.refresh_tokens.get_by_hash(hash_token(cookie_token))
            if saved is None:
                raise InvalidRefreshTokenError("Log in again.")
            if saved.replaced_by_id is not None:
                await uow.refresh_tokens.revoke_all_for_user(saved.user_id, now)
                # Committed before refusing: raising would otherwise roll the lockout back.
                await uow.commit()
                raise InvalidRefreshTokenError("Log in again.")
            if not saved.is_active(now):  # logged out, or past its 7 days
                raise InvalidRefreshTokenError("Log in again.")
            user = await uow.users.get(saved.user_id)
            if user is None:
                raise InvalidRefreshTokenError("Log in again.")

            new, new_cookie_token = saved.rotate(now)
            await uow.refresh_tokens.add(new)  # first, so the old row can point at it
            await uow.refresh_tokens.save(saved)
            await uow.commit()

        return LoginResult(
            access_token=self._tokens.issue(user, now),
            expires_in=int(self._tokens.lifetime.total_seconds()),
            refresh_token=new_cookie_token,
        )


class LogOut:
    """POST /auth/logout: always succeeds (204). If the cookie is a session still in use,
    it stops working; the endpoint clears the cookie either way."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, cookie_token: str | None) -> None:
        if not cookie_token:
            return
        async with self._uow as uow:
            saved = await uow.refresh_tokens.get_by_hash(hash_token(cookie_token))
            if saved is None or saved.revoked_at is not None:
                return
            saved.revoke(self._clock.now())
            await uow.refresh_tokens.save(saved)
            await uow.commit()
