"""SqlVerificationTokenRepository against a real PostgreSQL (#5)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import users
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.adapters.persistence.verification_token_repository import (
    SqlVerificationTokenRepository,
)
from accounts.domain.email import Email
from accounts.domain.user import User
from accounts.domain.verification import VerificationToken, hash_token

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


async def saved_user(session: AsyncSession, email: str = "ada@myumanitoba.ca") -> User:
    user = User.register(Email.parse(email), "argon2-hash", "Ada", "Lovelace")
    await SqlUserRepository(session).add(user)
    return user


async def test_a_saved_token_can_be_found_by_its_hash(session: AsyncSession) -> None:
    user = await saved_user(session)
    token, link_token = VerificationToken.issue(user.id, NOW)
    await SqlVerificationTokenRepository(session).add(token)
    await session.commit()

    async with AsyncSession(session.bind) as fresh:
        found = await SqlVerificationTokenRepository(fresh).get_by_hash(hash_token(link_token))
    assert found == token


async def test_an_unknown_hash_is_none(session: AsyncSession) -> None:
    repository = SqlVerificationTokenRepository(session)

    assert await repository.get_by_hash(hash_token("not-a-real-token")) is None


async def test_saving_a_token_stores_that_it_was_used(session: AsyncSession) -> None:
    user = await saved_user(session)
    token, _ = VerificationToken.issue(user.id, NOW)
    repository = SqlVerificationTokenRepository(session)
    await repository.add(token)

    token.consume(NOW + timedelta(minutes=5))
    await repository.save(token)
    await session.commit()

    async with AsyncSession(session.bind) as fresh:
        found = await SqlVerificationTokenRepository(fresh).get_by_hash(token.token_hash)
    assert found is not None
    assert found.consumed_at == NOW + timedelta(minutes=5)


async def test_a_resend_uses_up_only_that_users_unused_tokens(session: AsyncSession) -> None:
    ada = await saved_user(session, "ada@myumanitoba.ca")
    grace = await saved_user(session, "grace@myumanitoba.ca")
    repository = SqlVerificationTokenRepository(session)
    old_used, _ = VerificationToken.issue(ada.id, NOW)
    old_used.consume(NOW + timedelta(minutes=1))
    old_unused, _ = VerificationToken.issue(ada.id, NOW)
    graces, _ = VerificationToken.issue(grace.id, NOW)
    for token in (old_used, old_unused, graces):
        await repository.add(token)

    resent_at = NOW + timedelta(hours=1)
    await repository.consume_active_for_user(ada.id, resent_at)

    tokens = (old_used, old_unused, graces)
    found = {t.id: await repository.get_by_hash(t.token_hash) for t in tokens}
    assert found[old_unused.id] is not None
    assert found[old_unused.id].consumed_at == resent_at
    assert found[old_used.id] is not None
    assert found[old_used.id].consumed_at == NOW + timedelta(minutes=1)  # unchanged
    assert found[graces.id] is not None
    assert found[graces.id].consumed_at is None  # someone else's link still works


async def test_deleting_a_user_deletes_their_tokens(session: AsyncSession) -> None:
    user = await saved_user(session)
    token, _ = VerificationToken.issue(user.id, NOW)
    repository = SqlVerificationTokenRepository(session)
    await repository.add(token)

    await session.execute(delete(users).where(users.c.id == user.id))

    assert await repository.get_by_hash(token.token_hash) is None


async def test_a_token_being_checked_is_locked(session: AsyncSession) -> None:
    """Two clicks on the same link at once: the second has to wait for the first."""
    user = await saved_user(session)
    token, _ = VerificationToken.issue(user.id, NOW)
    await SqlVerificationTokenRepository(session).add(token)
    await session.commit()

    await SqlVerificationTokenRepository(session).get_by_hash(token.token_hash)  # locks it
    async with AsyncSession(session.bind) as second:
        await second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(DBAPIError, match="lock timeout"):
            await SqlVerificationTokenRepository(second).get_by_hash(token.token_hash)
    await session.rollback()
