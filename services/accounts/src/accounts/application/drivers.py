"""Use cases for applying to drive (#8)."""

from uuid import UUID

from accounts.application.ports import UnitOfWork
from accounts.domain.driver import DriverProfile, Vehicle


class GetMyDriverProfile:
    """GET /me/driver (#10): where the logged-in student's application stands. A student
    who has never applied gets status "none", not a 404."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> DriverProfile:
        async with self._uow as uow:
            return await uow.drivers.get(user_id) or DriverProfile(user_id)


class SaveVehicle:
    """PUT /me/driver/vehicle (#125): saves or changes the student's vehicle. Allowed at any
    status, and it doesn't send an approved driver back for review. 422 invalid_input names
    each invalid field."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(
        self, user_id: UUID, make: str, model: str, colour: str, plate: str
    ) -> DriverProfile:
        vehicle = Vehicle.create(make, model, colour, plate)  # 422 before anything is saved
        async with self._uow as uow:
            profile = await uow.drivers.get(user_id, for_update=True) or DriverProfile(user_id)
            profile.save_vehicle(vehicle)
            await uow.drivers.save(profile)
            await uow.commit()
        return profile
