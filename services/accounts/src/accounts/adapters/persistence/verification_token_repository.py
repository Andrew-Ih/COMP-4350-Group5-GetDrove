"""The PostgreSQL ``VerificationTokenRepository``: tokens in accounts.verification_tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import verification_tokens
from accounts.domain.verification import VerificationToken


class SqlVerificationTokenRepository:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: VerificationToken) -> None:
        await self._session.execute(
            insert(verification_tokens).values(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                consumed_at=token.consumed_at,
            )
        )

    async def get_by_hash(self, token_hash: str) -> VerificationToken | None:
        row = (
            await self._session.execute(
                select(verification_tokens)
                .where(verification_tokens.c.token_hash == token_hash)
                # Locks the row: a second request for the same link waits, then sees it used.
                .with_for_update()
            )
        ).first()
        return _to_token(row) if row else None

    async def save(self, token: VerificationToken) -> None:
        await self._session.execute(
            update(verification_tokens)
            .where(verification_tokens.c.id == token.id)
            .values(consumed_at=token.consumed_at)
        )

    async def consume_active_for_user(self, user_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(verification_tokens)
            .where(
                verification_tokens.c.user_id == user_id,
                verification_tokens.c.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )


def _to_token(row: Row[tuple[object, ...]]) -> VerificationToken:
    data = row._mapping
    return VerificationToken(
        id=data["id"],
        user_id=data["user_id"],
        token_hash=data["token_hash"],
        expires_at=data["expires_at"],
        consumed_at=data["consumed_at"],
    )
