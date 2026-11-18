"""The PostgreSQL ``ReputationRepository``: ratings, trips and no-shows in
accounts.reputation (#143)."""

from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import reputation
from accounts.domain.reputation import Reputation


class SqlReputationRepository:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_many(self, user_ids: Collection[UUID]) -> dict[UUID, Reputation]:
        if not user_ids:
            return {}
        rows = await self._session.execute(
            select(reputation).where(reputation.c.user_id.in_(user_ids))
        )
        return {
            row.user_id: Reputation(
                user_id=row.user_id,
                rating_sum=row.rating_sum,
                rating_count=row.rating_count,
                trip_count=row.trip_count,
                no_show_count=row.no_show_count,
            )
            for row in rows
        }
