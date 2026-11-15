"""The PostgreSQL ``DriverProfileRepository``: applications to drive in
accounts.driver_profiles."""

from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from accounts.adapters.persistence.tables import driver_profiles
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle


class SqlDriverProfileRepository:
    """Works inside the caller's session and never commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID, *, for_update: bool = False) -> DriverProfile | None:
        query = select(driver_profiles).where(driver_profiles.c.user_id == user_id)
        if for_update:
            # Two admins deciding at once, or an upload during a decision: the second waits,
            # then sees the first one's result.
            query = query.with_for_update()
        row = (await self._session.execute(query)).first()
        return _to_profile(row) if row else None

    async def save(self, profile: DriverProfile) -> None:
        values = _to_row(profile)
        statement = insert(driver_profiles).values(**values)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[driver_profiles.c.user_id],
                set_={key: statement.excluded[key] for key in values if key != "user_id"},
            )
        )


def _to_row(profile: DriverProfile) -> dict[str, object]:
    vehicle = profile.vehicle
    return {
        "user_id": profile.user_id,
        "status": profile.status.value,
        "licence_key": profile.licence_key,
        "insurance_key": profile.insurance_key,
        "vehicle_make": vehicle.make if vehicle else None,
        "vehicle_model": vehicle.model if vehicle else None,
        "vehicle_colour": vehicle.colour if vehicle else None,
        "vehicle_plate": vehicle.plate if vehicle else None,
        "submitted_at": profile.submitted_at,
        "reviewed_at": profile.reviewed_at,
        "reviewed_by": profile.reviewed_by,
        "rejection_reason": profile.rejection_reason,
    }


def _to_profile(row: Row[tuple[object, ...]]) -> DriverProfile:
    data = row._mapping
    vehicle = (
        Vehicle(
            make=data["vehicle_make"],
            model=data["vehicle_model"],
            colour=data["vehicle_colour"],
            plate=data["vehicle_plate"],
        )
        if data["vehicle_plate"] is not None
        else None
    )
    return DriverProfile(
        user_id=data["user_id"],
        status=DriverStatus(data["status"]),
        licence_key=data["licence_key"],
        insurance_key=data["insurance_key"],
        vehicle=vehicle,
        submitted_at=data["submitted_at"],
        reviewed_at=data["reviewed_at"],
        reviewed_by=data["reviewed_by"],
        rejection_reason=data["rejection_reason"],
    )
