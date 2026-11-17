"""Applying to drive (#8), with in-memory fakes instead of a database."""

from uuid import uuid4

from accounts.application.drivers import GetMyDriverProfile
from accounts.domain.driver import DriverProfile, DriverStatus
from accounts.testing import FIXED_NOW, FakeUnitOfWork


async def test_a_student_who_never_applied_has_status_none() -> None:
    user_id = uuid4()

    profile = await GetMyDriverProfile(FakeUnitOfWork())(user_id)

    assert profile == DriverProfile(user_id)
    assert profile.status is DriverStatus.NONE


async def test_a_student_sees_their_own_application() -> None:
    uow = FakeUnitOfWork()
    mine = DriverProfile(uuid4())
    mine.submit_documents("licence", "insurance", FIXED_NOW)
    await uow.drivers.save(mine)
    await uow.drivers.save(DriverProfile(uuid4()))  # someone else's

    profile = await GetMyDriverProfile(uow)(mine.user_id)

    assert profile.status is DriverStatus.PENDING
    assert profile.submitted_at == FIXED_NOW
