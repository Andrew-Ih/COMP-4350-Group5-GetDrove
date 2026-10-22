"""The sign-up use case (#4)."""

from accounts.application.ports import Clock, PasswordHasher, UnitOfWork
from accounts.application.verification import issue_verification_token
from accounts.domain.email import Email
from accounts.domain.user import User
from events.catalog import UserRegistered


class SignUp:
    """POST /auth/signup: creates an unverified account and asks Notifications to send the
    verification email.

    422 email_not_uofm (another domain) or invalid_input (a typo, a blank name), and 409
    email_taken. The password's 10-128 characters are checked by the request model first.
    """

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def __call__(self, email: str, password: str, first_name: str, last_name: str) -> User:
        parsed = Email.parse(email)
        # Hashing is slow on purpose (ADR 0020), so it happens before the transaction opens.
        user = User.register(parsed, self._hasher.hash(password), first_name, last_name)

        async with self._uow as uow:
            await uow.users.add(user)  # 409 email_taken for a duplicate
            link_token = await issue_verification_token(uow, user, self._clock)
            await uow.events.publish(
                UserRegistered(
                    user_id=user.id,
                    email=user.email.value,
                    first_name=user.first_name,
                    verification_token=link_token,
                )
            )
            await uow.commit()
        return user
