"""Use case: create verified demo accounts (#111), for the demo and for testing by hand.

Unlike sign-up, it publishes no UserRegistered event, so no verification email is sent:
on the live site those would go to made-up addresses and bounce. Existing accounts are
left alone, so running it again is safe.
"""

from dataclasses import dataclass, field

from accounts.application.ports import Clock, PasswordHasher, UnitOfWork
from accounts.domain.email import Email
from accounts.domain.user import User
from common_web import InvalidField, InvalidInputError

MIN_PASSWORD_LENGTH = 10  # the contract's SignupRequest.password minimum


@dataclass(frozen=True)
class DemoAccount:
    email: str
    first_name: str
    last_name: str


@dataclass
class SeedResult:
    created: list[str] = field(default_factory=list)
    already_there: list[str] = field(default_factory=list)


class SeedAccounts:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def __call__(self, accounts: list[DemoAccount], password: str) -> SeedResult:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidInputError(
                f"The demo password must be at least {MIN_PASSWORD_LENGTH} characters.",
                [InvalidField("password", f"At least {MIN_PASSWORD_LENGTH} characters")],
            )
        # Checked before anything is saved, so a mistake doesn't leave half the accounts.
        emails = [Email.parse(account.email) for account in accounts]
        password_hash = self._hasher.hash(password)  # one hash: every demo account shares it

        result = SeedResult()
        async with self._uow as uow:
            for account, email in zip(accounts, emails, strict=True):
                if await uow.users.get_by_email(email) is not None:
                    result.already_there.append(email.value)
                    continue
                user = User.register(email, password_hash, account.first_name, account.last_name)
                user.email_verified_at = self._clock.now()
                await uow.users.add(user)
                result.created.append(email.value)
            await uow.commit()
        return result
