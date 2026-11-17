"""PostgreSQL implementation of ``TripMembers`` (#146)."""

from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notifications.adapters.persistence.tables import trip_members
from notifications.domain.trip_members import TripMember, TripRole


class SQLAlchemyTripMembers:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_driver(self, trip_id: UUID, driver_id: UUID) -> None:
        await self.session.execute(
            insert(trip_members)
            .values(trip_id=trip_id, user_id=driver_id, role=TripRole.DRIVER.value, active=True)
            .on_conflict_do_nothing(index_elements=[trip_members.c.trip_id, trip_members.c.user_id])
        )

    async def add_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        statement = insert(trip_members).values(
            trip_id=trip_id, user_id=rider_id, role=TripRole.RIDER.value, active=True
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[trip_members.c.trip_id, trip_members.c.user_id],
                set_={"active": True, "updated_at": func.now()},
            )
        )

    async def remove_rider(self, trip_id: UUID, rider_id: UUID) -> None:
        await self.session.execute(
            update(trip_members)
            .where(
                trip_members.c.trip_id == trip_id,
                trip_members.c.user_id == rider_id,
                trip_members.c.role == TripRole.RIDER.value,
            )
            .values(active=False, updated_at=func.now())
        )

    async def end_trip(self, trip_id: UUID) -> None:
        await self.session.execute(
            update(trip_members)
            .where(trip_members.c.trip_id == trip_id, trip_members.c.active.is_(True))
            .values(active=False, updated_at=func.now())
        )

    async def active(self, trip_id: UUID) -> list[TripMember]:
        driver_first = case((trip_members.c.role == TripRole.DRIVER.value, 0), else_=1)
        rows = await self.session.execute(
            select(trip_members)
            .where(trip_members.c.trip_id == trip_id, trip_members.c.active.is_(True))
            .order_by(driver_first, trip_members.c.user_id)
        )
        return [
            TripMember(
                trip_id=row["trip_id"],
                user_id=row["user_id"],
                role=TripRole(row["role"]),
                active=row["active"],
            )
            for row in rows.mappings()
        ]
