"""The PostgreSQL ``UserRepository``: turns ``User`` objects into rows of accounts.users and
back."""

from uuid import UUID

from sqlalchemy import Row, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import users
from accounts.domain.email import Email
from accounts.domain.errors import EmailTakenError
from accounts.domain.user import User


class SqlUserRepository:
    """Works inside the caller's session and never commits, so a user and the events
    about it (outbox) are saved together or not at all."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        try:
            # A savepoint: if the insert fails, only it is undone, not the whole transaction.
            async with self._session.begin_nested():
                await self._session.execute(
                    insert(users).values(
                        id=user.id,
                        email=user.email.value,
                        password_hash=user.password_hash,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        email_verified_at=user.email_verified_at,
                        is_admin=user.is_admin,
                    )
                )
        except IntegrityError as exc:
            # The unique index on email is what catches duplicates, even two sign-ups at
            # the same moment. Emails are stored lowercase, so it ignores case.
            if _constraint_name(exc) == "uq_users_email":
                raise EmailTakenError("An account with this email already exists") from exc
            raise

    async def get(self, user_id: UUID) -> User | None:
        row = (await self._session.execute(select(users).where(users.c.id == user_id))).first()
        return _to_user(row) if row else None

    async def get_by_email(self, email: Email) -> User | None:
        row = (
            await self._session.execute(select(users).where(users.c.email == email.value))
        ).first()
        return _to_user(row) if row else None

    async def save(self, user: User) -> None:
        # The email never changes after sign-up, so it isn't updated here.
        await self._session.execute(
            update(users)
            .where(users.c.id == user.id)
            .values(
                password_hash=user.password_hash,
                first_name=user.first_name,
                last_name=user.last_name,
                email_verified_at=user.email_verified_at,
                is_admin=user.is_admin,
            )
        )


def _constraint_name(exc: IntegrityError) -> str | None:
    """The name of the constraint Postgres says was violated.

    Read from the error's field rather than its message, whose wording can change between
    library versions. SQLAlchemy's asyncpg adapter wraps asyncpg's error, and the field is on
    the original (``exc.orig.__cause__``), not on the wrapper.
    """
    return getattr(exc.orig.__cause__, "constraint_name", None) if exc.orig else None


def _to_user(row: Row[tuple[object, ...]]) -> User:
    data = row._mapping
    return User(
        id=data["id"],
        email=Email(data["email"]),  # already checked and lowercased when it was saved
        password_hash=data["password_hash"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        email_verified_at=data["email_verified_at"],
        is_admin=data["is_admin"],
    )
