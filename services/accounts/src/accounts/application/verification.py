"""Use cases for email verification (#5): verifying a link, and sending a new one."""

from accounts.application.ports import Clock, UnitOfWork
from accounts.domain.email import Email
from accounts.domain.errors import InvalidVerificationTokenError
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken, hash_token
from common_web import InvalidInputError
from events.catalog import VerificationEmailRequested


async def issue_verification_token(uow: UnitOfWork, user: User, clock: Clock) -> str:
    """Saves a new 24-hour token for ``user`` and returns the token for the email's link.
    Shared by sign-up (#4) and resend. The caller publishes the event and commits."""
    token, link_token = VerificationToken.issue(user.id, clock.now())
    await uow.verification_tokens.add(token)
    return link_token


class VerifyEmail:
    """POST /auth/verify: 204, or 400 invalid_token (unknown or used), or 410 token_expired."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, token: str) -> None:
        async with self._uow as uow:
            saved = await uow.verification_tokens.get_by_hash(hash_token(token))
            if saved is None:
                raise InvalidVerificationTokenError("This verification link isn't valid.")
            now = self._clock.now()
            saved.consume(now)  # 400 if already used, 410 if expired
            await uow.verification_tokens.save(saved)

            user = await uow.users.get(saved.user_id)
            if user is not None and not user.email_verified:
                user.email_verified_at = now
                await uow.users.save(user)
            await uow.commit()


class ResendVerification:
    """POST /auth/resend-verification: always 202.

    Unknown, already-verified and invalid emails quietly do nothing, so the endpoint can't
    be used to find out who has an account. Otherwise older links stop working, a new one
    is issued, and Notifications is asked to email it.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, email: str) -> None:
        try:
            parsed = Email.parse(email)
        except InvalidInputError:
            return

        async with self._uow as uow:
            user = await uow.users.get_by_email(parsed)
            if user is None or user.email_verified:
                return
            await uow.verification_tokens.consume_active_for_user(user.id, self._clock.now())
            link_token = await issue_verification_token(uow, user, self._clock)
            await uow.events.publish(
                VerificationEmailRequested(
                    user_id=user.id,
                    email=user.email.value,
                    first_name=user.first_name,
                    verification_token=link_token,
                )
            )
            await uow.commit()
