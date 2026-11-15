"""Applying to drive (#8), with in-memory fakes instead of a database."""

from uuid import uuid4

import pytest

from accounts.application.drivers import GetMyDriverProfile, SaveVehicle
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.testing import FIXED_NOW, FakeUnitOfWork
from common_web import InvalidInputError


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


# ---------------------------------------------------------------- the vehicle (#125)


async def test_saving_a_vehicle_before_applying_keeps_status_none() -> None:
    uow = FakeUnitOfWork()
    user_id = uuid4()

    profile = await SaveVehicle(uow)(user_id, "Honda", "Civic", "Blue", "abc123")

    assert profile.vehicle == Vehicle("Honda", "Civic", "Blue", "ABC123")
    assert profile.status is DriverStatus.NONE
    assert uow.drivers.rows[user_id] == profile
    assert uow.committed


async def test_an_approved_driver_can_change_their_vehicle_and_stays_approved() -> None:
    uow = FakeUnitOfWork()
    driver = DriverProfile(uuid4(), vehicle=Vehicle.create("Honda", "Civic", "Blue", "ABC123"))
    driver.submit_documents("licence", "insurance", FIXED_NOW)
    driver.approve(uuid4(), FIXED_NOW)
    await uow.drivers.save(driver)

    profile = await SaveVehicle(uow)(driver.user_id, "Toyota", "Corolla", "Grey", "XYZ9")

    assert profile.status is DriverStatus.APPROVED
    assert profile.vehicle == Vehicle("Toyota", "Corolla", "Grey", "XYZ9")
    assert profile.licence_key == "licence"


async def test_an_invalid_vehicle_saves_nothing() -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(InvalidInputError):
        await SaveVehicle(uow)(uuid4(), "Honda", "", "Blue", "ABC123")

    assert uow.drivers.rows == {}
    assert not uow.committed
