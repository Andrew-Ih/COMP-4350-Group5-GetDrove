"""SQLAlchemy implementation of the auto-accept rules repository (#42)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import auto_accept_rules
from trips.domain.auto_accept import AutoAcceptRules


class SQLAlchemyAutoAcceptRulesRepository:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, driver_id: UUID) -> AutoAcceptRules | None:
        row = (
            (
                await self.session.execute(
                    select(auto_accept_rules).where(auto_accept_rules.c.driver_id == driver_id)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return AutoAcceptRules(
            enabled=row["enabled"],
            max_detour_minutes=row["max_detour_minutes"],
            min_rating=row["min_rating"],
        )

    async def save(self, driver_id: UUID, rules: AutoAcceptRules) -> None:
        values = {
            "enabled": rules.enabled,
            "max_detour_minutes": rules.max_detour_minutes,
            "min_rating": rules.min_rating,
        }
        # Insert, or replace the driver's existing rules: one statement, so two saves at
        # once can't both try to insert.
        await self.session.execute(
            insert(auto_accept_rules)
            .values(driver_id=driver_id, **values)
            .on_conflict_do_update(index_elements=[auto_accept_rules.c.driver_id], set_=values)
        )
