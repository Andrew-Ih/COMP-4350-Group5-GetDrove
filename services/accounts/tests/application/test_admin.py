"""Admins reviewing applications to drive (#127), with in-memory fakes."""

from datetime import timedelta
from uuid import uuid4

import pytest

from accounts.application.admin import (
    ApproveDriver,
    ListDriverApplications,
    MakeAdmin,
    RejectDriver,
)
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.email import Email
from accounts.domain.errors import (
    DriverNotFoundError,
    DriverNotPendingError,
    EmailNotUofMError,
    UserNotFoundError,
    VehicleMissingError,
)
from accounts.domain.user import User
from accounts.testing import FIXED_NOW, FakeClock, FakeUnitOfWork
from events.catalog import DriverApproved, DriverRejected

ADMIN = uuid4()
CIVIC = Vehicle.create("Honda", "Civic", "Blue", "ABC123")


async def applicant(
    uow: FakeUnitOfWork,
    name: str,
    *,
    submitted_minutes_ago: int = 0,
    vehicle: bool = True,
    status: DriverStatus = DriverStatus.PENDING,
) -> User:
    user = User.register(Email.parse(f"{name}@myumanitoba.ca"), "hash", name.title(), "Test")
    await uow.users.add(user)
    profile = DriverProfile(user.id, vehicle=CIVIC if vehicle else None)
    if status is not DriverStatus.NONE:
        submitted = FIXED_NOW - timedelta(minutes=submitted_minutes_ago)
        profile.submit_documents("licence", "insurance", submitted)
    if status is DriverStatus.APPROVED:
        profile.approve(ADMIN, FIXED_NOW)
    await uow.drivers.save(profile)
    return user


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


# ---------------------------------------------------------------- the list


async def test_pending_applications_are_listed_oldest_first_with_their_names(
    uow: FakeUnitOfWork,
) -> None:
    newer = await applicant(uow, "newer", submitted_minutes_ago=5)
    older = await applicant(uow, "older", submitted_minutes_ago=60)
    await applicant(uow, "approved", status=DriverStatus.APPROVED)
    await applicant(uow, "never", status=DriverStatus.NONE)

    applications = await ListDriverApplications(uow)(DriverStatus.PENDING)

    assert [a.user.id for a in applications] == [older.id, newer.id]
    assert applications[0].user.email.value == "older@myumanitoba.ca"


async def test_listing_by_another_status(uow: FakeUnitOfWork) -> None:
    approved = await applicant(uow, "approved", status=DriverStatus.APPROVED)
    await applicant(uow, "pending")

    applications = await ListDriverApplications(uow)(DriverStatus.APPROVED)

    assert [a.user.id for a in applications] == [approved.id]


# ---------------------------------------------------------------- approving


async def test_approving_saves_the_decision_and_publishes_driver_approved(
    uow: FakeUnitOfWork,
) -> None:
    ada = await applicant(uow, "ada")

    application = await ApproveDriver(uow, FakeClock())(ADMIN, ada.id)

    saved = uow.drivers.rows[ada.id]
    assert saved.status is DriverStatus.APPROVED
    assert (saved.reviewed_at, saved.reviewed_by) == (FIXED_NOW, ADMIN)
    assert uow.events.published == [DriverApproved(user_id=ada.id)]
    assert uow.committed
    assert application.profile == saved
    assert application.user.id == ada.id


async def test_approving_without_a_vehicle_is_refused_and_publishes_nothing(
    uow: FakeUnitOfWork,
) -> None:
    ada = await applicant(uow, "ada", vehicle=False)

    with pytest.raises(VehicleMissingError):
        await ApproveDriver(uow, FakeClock())(ADMIN, ada.id)

    assert uow.drivers.rows[ada.id].status is DriverStatus.PENDING
    assert uow.events.published == []
    assert not uow.committed


async def test_approving_twice_is_refused(uow: FakeUnitOfWork) -> None:
    ada = await applicant(uow, "ada")
    await ApproveDriver(uow, FakeClock())(ADMIN, ada.id)

    with pytest.raises(DriverNotPendingError):
        await ApproveDriver(uow, FakeClock())(ADMIN, ada.id)

    assert len(uow.events.published) == 1


@pytest.mark.parametrize("decide", ["approve", "reject"])
async def test_a_student_who_never_applied_is_not_found(uow: FakeUnitOfWork, decide: str) -> None:
    # One only saved a vehicle (a profile with status none); the other has no profile.
    vehicle_only = await applicant(uow, "vehicle", status=DriverStatus.NONE)

    for user_id in (vehicle_only.id, uuid4()):
        with pytest.raises(DriverNotFoundError):
            if decide == "approve":
                await ApproveDriver(uow, FakeClock())(ADMIN, user_id)
            else:
                await RejectDriver(uow, FakeClock())(ADMIN, user_id, "No.")

    assert uow.events.published == []


# ---------------------------------------------------------------- rejecting


async def test_rejecting_saves_the_reason_and_publishes_it(uow: FakeUnitOfWork) -> None:
    ada = await applicant(uow, "ada")

    application = await RejectDriver(uow, FakeClock())(
        ADMIN, ada.id, "  The insurance has expired.  "
    )

    saved = uow.drivers.rows[ada.id]
    assert saved.status is DriverStatus.REJECTED
    assert saved.rejection_reason == "The insurance has expired."
    assert uow.events.published == [
        DriverRejected(user_id=ada.id, reason="The insurance has expired.")
    ]
    assert uow.committed
    assert application.profile.rejection_reason == "The insurance has expired."


async def test_rejecting_an_approved_driver_is_refused(uow: FakeUnitOfWork) -> None:
    ada = await applicant(uow, "ada", status=DriverStatus.APPROVED)

    with pytest.raises(DriverNotPendingError):
        await RejectDriver(uow, FakeClock())(ADMIN, ada.id, "Changed my mind.")

    assert uow.events.published == []


# ---------------------------------------------------------------- making an admin


async def test_make_admin_gives_the_admin_role(uow: FakeUnitOfWork) -> None:
    ada = await applicant(uow, "ada", status=DriverStatus.NONE)

    user = await MakeAdmin(uow)("Ada@MyUManitoba.ca")

    assert user.roles == ["user", "admin"]
    assert uow.users.rows[ada.id].is_admin
    assert uow.committed


async def test_make_admin_on_an_admin_changes_nothing(uow: FakeUnitOfWork) -> None:
    ada = await applicant(uow, "ada", status=DriverStatus.NONE)
    await MakeAdmin(uow)(ada.email.value)
    uow.committed = False

    await MakeAdmin(uow)(ada.email.value)

    assert not uow.committed


async def test_make_admin_needs_an_existing_uofm_account(uow: FakeUnitOfWork) -> None:
    with pytest.raises(UserNotFoundError):
        await MakeAdmin(uow)("nobody@myumanitoba.ca")
    with pytest.raises(EmailNotUofMError):
        await MakeAdmin(uow)("someone@gmail.com")
