"""Public profiles and the internal user lookup (#143), with in-memory fakes."""

from uuid import uuid4

import pytest

from accounts.application.profiles import GetPublicProfile, LookUpUsers
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.email import Email
from accounts.domain.errors import UserNotFoundError
from accounts.domain.reputation import Reputation
from accounts.domain.user import User
from accounts.testing import FakeUnitOfWork

CIVIC = Vehicle.create("Honda", "Civic", "Blue", "ABC123")


async def student(
    uow: FakeUnitOfWork, name: str, *, driver: DriverStatus = DriverStatus.NONE
) -> User:
    """A student, optionally with an application to drive in the given state."""
    user = User.register(Email.parse(f"{name}@myumanitoba.ca"), "hash", name.title(), "Test")
    await uow.users.add(user)
    if driver is not DriverStatus.NONE:
        await uow.drivers.save(DriverProfile(user.id, status=driver, vehicle=CIVIC))
    return user


async def test_a_new_student_has_zeros_and_no_vehicle() -> None:
    uow = FakeUnitOfWork()
    ada = await student(uow, "ada")

    summary = await GetPublicProfile(uow)(ada.id)

    assert summary.user.first_name == "Ada"
    assert summary.reputation == Reputation(ada.id)
    assert (summary.is_driver, summary.vehicle) == (False, None)


async def test_an_approved_driver_shows_their_vehicle() -> None:
    uow = FakeUnitOfWork()
    maya = await student(uow, "maya", driver=DriverStatus.APPROVED)

    summary = await GetPublicProfile(uow)(maya.id)

    assert summary.is_driver
    assert summary.vehicle == CIVIC


@pytest.mark.parametrize("status", [DriverStatus.PENDING, DriverStatus.REJECTED])
async def test_a_student_who_isnt_approved_shows_no_vehicle(status: DriverStatus) -> None:
    uow = FakeUnitOfWork()
    tom = await student(uow, "tom", driver=status)

    summary = await GetPublicProfile(uow)(tom.id)

    assert (summary.is_driver, summary.vehicle) == (False, None)


async def test_the_profile_uses_their_reputation() -> None:
    uow = FakeUnitOfWork()
    ada = await student(uow, "ada")
    uow.reputation.rows[ada.id] = Reputation(ada.id, rating_sum=9, rating_count=2, trip_count=4)

    summary = await GetPublicProfile(uow)(ada.id)

    assert (summary.reputation.rating, summary.reputation.trip_count) == (4.5, 4)


async def test_an_unknown_user_is_not_found() -> None:
    with pytest.raises(UserNotFoundError):
        await GetPublicProfile(FakeUnitOfWork())(uuid4())


async def test_the_lookup_returns_users_in_the_order_asked_each_once() -> None:
    uow = FakeUnitOfWork()
    ada, maya = await student(uow, "ada"), await student(uow, "maya")

    found = await LookUpUsers(uow)([maya.id, uuid4(), ada.id, maya.id])

    # The unknown ID is left out, and Maya, asked for twice, appears once.
    assert [summary.user.id for summary in found] == [maya.id, ada.id]


async def test_the_lookup_includes_approved_drivers_vehicles_and_no_shows() -> None:
    uow = FakeUnitOfWork()
    maya = await student(uow, "maya", driver=DriverStatus.APPROVED)
    noah = await student(uow, "noah")
    uow.reputation.rows[noah.id] = Reputation(noah.id, no_show_count=2)

    by_id = {s.user.id: s for s in await LookUpUsers(uow)([maya.id, noah.id])}

    assert by_id[maya.id].vehicle == CIVIC
    assert by_id[noah.id].vehicle is None
    assert by_id[noah.id].reputation.no_show_count == 2
