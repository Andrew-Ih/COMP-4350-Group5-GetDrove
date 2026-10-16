"""The PostgreSQL ``RefreshTokenRepository``: tokens in accounts.refresh_tokens."""

from sqlalchemy import Row, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import refresh_tokens
from accounts.domain.refresh_token import RefreshToken


class SqlRefreshTokenRepository:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> None:
        await self._session.execute(
            insert(refresh_tokens).values(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                replaced_by_id=token.replaced_by_id,
            )
        )

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        row = (
            await self._session.execute(
                select(refresh_tokens)
                .where(refresh_tokens.c.token_hash == token_hash)
                # Locks the row: a second request with the same token waits, then sees it swapped.
                .with_for_update()
            )
        ).first()
        return _to_token(row) if row else None


def _to_token(row: Row[tuple[object, ...]]) -> RefreshToken:
    data = row._mapping
    return RefreshToken(
        id=data["id"],
        user_id=data["user_id"],
        token_hash=data["token_hash"],
        expires_at=data["expires_at"],
        revoked_at=data["revoked_at"],
        replaced_by_id=data["replaced_by_id"],
    )
