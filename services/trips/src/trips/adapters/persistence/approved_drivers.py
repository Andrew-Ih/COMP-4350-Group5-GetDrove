"""The PostgreSQL ``ApprovedDrivers``: trips.approved_drivers (#11)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trips.adapters.persistence.tables import approved_drivers


class SQLAlchemyApprovedDrivers:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_approved(self, driver_id: UUID) -> bool:
        found = await self._session.scalar(
            select(approved_drivers.c.driver_id).where(approved_drivers.c.driver_id == driver_id)
        )
        return found is not None

    async def approve(self, driver_id: UUID, approved_at: datetime) -> None:
        # Already on the list (e.g. approved again after new documents): keep the first time.
        await self._session.execute(
            insert(approved_drivers)
            .values(driver_id=driver_id, approved_at=approved_at)
            .on_conflict_do_nothing(index_elements=[approved_drivers.c.driver_id])
        )

    async def remove(self, driver_id: UUID) -> None:
        await self._session.execute(
            delete(approved_drivers).where(approved_drivers.c.driver_id == driver_id)
        )
