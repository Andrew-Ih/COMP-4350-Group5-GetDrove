"""Use cases for applying to drive (#8)."""

from uuid import UUID

from accounts.application.ports import UnitOfWork
from accounts.domain.driver import DriverProfile


class GetMyDriverProfile:
    """GET /me/driver (#10): where the logged-in student's application stands. A student
    who has never applied gets status "none", not a 404."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> DriverProfile:
        async with self._uow as uow:
            return await uow.drivers.get(user_id) or DriverProfile(user_id)
