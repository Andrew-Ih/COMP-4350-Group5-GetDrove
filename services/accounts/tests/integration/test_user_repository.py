"""SqlUserRepository against a real PostgreSQL (#3)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.domain.email import Email
from accounts.domain.errors import EmailTakenError
from accounts.domain.user import User


def ada(email: str = "ada@myumanitoba.ca") -> User:
    return User.register(Email.parse(email), "argon2-hash", "Ada", "Lovelace")


async def test_a_saved_user_can_be_found_by_id_and_email(session: AsyncSession) -> None:
    user = ada()
    await SqlUserRepository(session).add(user)
    await session.commit()

    # A brand-new session, so this really reads from the database.
    async with AsyncSession(session.bind) as fresh:
        repository = SqlUserRepository(fresh)
        assert await repository.get(user.id) == user
        assert await repository.get_by_email(user.email) == user


async def test_every_field_round_trips(session: AsyncSession) -> None:
    user = ada()
    user.email_verified_at = datetime(2026, 10, 14, 15, 30, tzinfo=UTC)
    user.is_admin = True
    repository = SqlUserRepository(session)

    await repository.add(user)
    found = await repository.get(user.id)

    assert found == user
    assert found is not None
    assert found.email_verified is True
    assert found.roles == ["user", "admin"]


async def test_finding_by_email_ignores_case(session: AsyncSession) -> None:
    repository = SqlUserRepository(session)
    await repository.add(ada("ada@myumanitoba.ca"))

    found = await repository.get_by_email(Email.parse("ADA@MyUManitoba.ca"))

    assert found is not None
    assert found.email.value == "ada@myumanitoba.ca"


@pytest.mark.parametrize("second_email", ["ada@myumanitoba.ca", "Ada@MYUMANITOBA.CA"])
async def test_a_second_account_with_the_same_email_is_refused(
    session: AsyncSession, second_email: str
) -> None:
    repository = SqlUserRepository(session)
    await repository.add(ada("ada@myumanitoba.ca"))

    with pytest.raises(EmailTakenError):
        await repository.add(ada(second_email))


async def test_a_refused_duplicate_doesnt_undo_the_rest_of_the_transaction(
    session: AsyncSession,
) -> None:
    repository = SqlUserRepository(session)
    first = ada("ada@myumanitoba.ca")
    await repository.add(first)

    with pytest.raises(EmailTakenError):
        await repository.add(ada("ada@myumanitoba.ca"))
    await session.commit()

    assert await repository.get(first.id) == first


async def test_other_database_errors_arent_reported_as_email_taken(
    session: AsyncSession,
) -> None:
    repository = SqlUserRepository(session)
    first = ada("ada@myumanitoba.ca")
    await repository.add(first)
    same_id = ada("grace@myumanitoba.ca")
    same_id.id = first.id

    with pytest.raises(IntegrityError, match="pk_users"):
        await repository.add(same_id)


async def test_unknown_users_are_none(session: AsyncSession) -> None:
    repository = SqlUserRepository(session)

    assert await repository.get(uuid4()) is None
    assert await repository.get_by_email(Email.parse("nobody@myumanitoba.ca")) is None
