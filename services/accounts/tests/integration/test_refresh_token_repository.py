"""SqlRefreshTokenRepository against a real PostgreSQL (#6)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.refresh_token_repository import SqlRefreshTokenRepository
from accounts.adapters.persistence.tables import users
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.domain.email import Email
from accounts.domain.refresh_token import RefreshToken
from accounts.domain.user import User
from accounts.domain.verification import hash_token

NOW = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)


async def saved_user(session: AsyncSession) -> User:
    user = User.register(Email.parse("ada@myumanitoba.ca"), "argon2-hash", "Ada", "Lovelace")
    await SqlUserRepository(session).add(user)
    return user


async def test_a_saved_token_can_be_found_by_the_cookies_hash(session: AsyncSession) -> None:
    user = await saved_user(session)
    token, cookie = RefreshToken.issue(user.id, NOW)
    await SqlRefreshTokenRepository(session).add(token)
    await session.commit()

    async with AsyncSession(session.bind) as fresh:
        found = await SqlRefreshTokenRepository(fresh).get_by_hash(hash_token(cookie))
    assert found == token


async def test_revoked_and_replaced_round_trip(session: AsyncSession) -> None:
    user = await saved_user(session)
    repository = SqlRefreshTokenRepository(session)
    newer, _ = RefreshToken.issue(user.id, NOW)
    await repository.add(newer)
    older, _ = RefreshToken.issue(user.id, NOW)
    older.revoked_at = NOW
    older.replaced_by_id = newer.id
    await repository.add(older)

    found = await repository.get_by_hash(older.token_hash)

    assert found == older


async def test_an_unknown_hash_is_none(session: AsyncSession) -> None:
    assert await SqlRefreshTokenRepository(session).get_by_hash(hash_token("nope")) is None


async def test_deleting_a_user_deletes_their_tokens(session: AsyncSession) -> None:
    user = await saved_user(session)
    token, _ = RefreshToken.issue(user.id, NOW)
    repository = SqlRefreshTokenRepository(session)
    await repository.add(token)

    await session.execute(delete(users).where(users.c.id == user.id))

    assert await repository.get_by_hash(token.token_hash) is None


async def test_a_token_being_used_is_locked(session: AsyncSession) -> None:
    """The same cookie sent twice at once: the second request has to wait for the first."""
    user = await saved_user(session)
    token, _ = RefreshToken.issue(user.id, NOW)
    await SqlRefreshTokenRepository(session).add(token)
    await session.commit()

    await SqlRefreshTokenRepository(session).get_by_hash(token.token_hash)  # locks it
    async with AsyncSession(session.bind) as second:
        await second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(DBAPIError, match="lock timeout"):
            await SqlRefreshTokenRepository(second).get_by_hash(token.token_hash)
    await session.rollback()
