"""Applying to drive (#8): every allowed and forbidden change of status (#10), and the
vehicle's rules (#125)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.errors import (
    DriverAlreadyApprovedError,
    DriverNotPendingError,
    VehicleMissingError,
)
from common_web import InvalidInputError

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)
ADMIN = uuid4()
CIVIC = Vehicle.create("Honda", "Civic", "Blue", "abc123")


def profile(status: DriverStatus = DriverStatus.NONE, *, vehicle: bool = True) -> DriverProfile:
    driver = DriverProfile(uuid4(), vehicle=CIVIC if vehicle else None)
    if status is not DriverStatus.NONE:
        driver.submit_documents("licence-key", "insurance-key", NOW)
    if status is DriverStatus.APPROVED:
        driver.approve(ADMIN, NOW)
    if status is DriverStatus.REJECTED:
        driver.reject(ADMIN, "Blurry licence.", NOW)
    return driver


def test_a_new_profile_has_not_applied() -> None:
    driver = DriverProfile(uuid4())

    assert driver.status is DriverStatus.NONE
    assert not driver.is_approved
    assert (driver.licence_key, driver.insurance_key, driver.vehicle) == (None, None, None)


# ---------------------------------------------------------------- uploading documents


@pytest.mark.parametrize("status", [DriverStatus.NONE, DriverStatus.PENDING, DriverStatus.REJECTED])
def test_uploading_documents_makes_the_application_pending(status: DriverStatus) -> None:
    driver = profile(status)

    driver.submit_documents("new-licence", "new-insurance", LATER)

    assert driver.status is DriverStatus.PENDING
    assert (driver.licence_key, driver.insurance_key) == ("new-licence", "new-insurance")
    assert driver.submitted_at == LATER
    assert driver.rejection_reason is None


def test_an_approved_driver_cant_replace_their_documents() -> None:
    driver = profile(DriverStatus.APPROVED)

    with pytest.raises(DriverAlreadyApprovedError):
        driver.submit_documents("new-licence", "new-insurance", LATER)

    assert driver.licence_key == "licence-key"


# ---------------------------------------------------------------- the admin's decision


def test_approving_a_pending_application() -> None:
    driver = profile(DriverStatus.PENDING)

    driver.approve(ADMIN, LATER)

    assert driver.status is DriverStatus.APPROVED
    assert driver.is_approved
    assert (driver.reviewed_at, driver.reviewed_by) == (LATER, ADMIN)


def test_rejecting_a_pending_application_keeps_the_trimmed_reason() -> None:
    driver = profile(DriverStatus.PENDING)

    driver.reject(ADMIN, "  The insurance has expired.  ", LATER)

    assert driver.status is DriverStatus.REJECTED
    assert driver.rejection_reason == "The insurance has expired."
    assert (driver.reviewed_at, driver.reviewed_by) == (LATER, ADMIN)


def test_approving_after_a_rejection_and_new_documents_clears_the_reason() -> None:
    driver = profile(DriverStatus.REJECTED)
    driver.submit_documents("new-licence", "new-insurance", LATER)

    driver.approve(ADMIN, LATER)

    assert driver.status is DriverStatus.APPROVED
    assert driver.rejection_reason is None


@pytest.mark.parametrize(
    "status", [DriverStatus.NONE, DriverStatus.APPROVED, DriverStatus.REJECTED]
)
def test_only_a_pending_application_can_be_decided(status: DriverStatus) -> None:
    driver = profile(status)

    with pytest.raises(DriverNotPendingError):
        driver.approve(ADMIN, LATER)
    with pytest.raises(DriverNotPendingError):
        driver.reject(ADMIN, "No.", LATER)

    assert driver.status is status


def test_approving_needs_a_vehicle() -> None:
    driver = profile(DriverStatus.PENDING, vehicle=False)

    with pytest.raises(VehicleMissingError):
        driver.approve(ADMIN, LATER)

    assert driver.status is DriverStatus.PENDING


def test_rejecting_doesnt_need_a_vehicle() -> None:
    driver = profile(DriverStatus.PENDING, vehicle=False)

    driver.reject(ADMIN, "Add your vehicle and upload a clearer licence.", LATER)

    assert driver.status is DriverStatus.REJECTED


@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
def test_a_rejection_needs_a_reason_of_up_to_500_characters(reason: str) -> None:
    driver = profile(DriverStatus.PENDING)

    with pytest.raises(InvalidInputError) as raised:
        driver.reject(ADMIN, reason, LATER)

    assert [error.field for error in raised.value.errors] == ["reason"]
    assert driver.status is DriverStatus.PENDING


# ---------------------------------------------------------------- the vehicle


def test_a_vehicle_is_trimmed_and_its_plate_uppercased() -> None:
    vehicle = Vehicle.create(" Honda ", " Civic", "Blue ", " abc123 ")

    assert vehicle == Vehicle("Honda", "Civic", "Blue", "ABC123")


@pytest.mark.parametrize(
    ("fields", "invalid"),
    [
        (("", "Civic", "Blue", "ABC123"), ["make"]),
        (("Honda", "   ", "Blue", "ABC123"), ["model"]),
        (("Honda", "Civic", "x" * 31, "ABC123"), ["colour"]),
        (("Honda", "Civic", "Blue", "A"), ["plate"]),
        (("Honda", "Civic", "Blue", "ABC 123"), ["plate"]),
        (("Honda", "Civic", "Blue", "ABCDE1234"), ["plate"]),
        (("", "", "", ""), ["make", "model", "colour", "plate"]),
    ],
)
def test_invalid_vehicles_name_every_bad_field(
    fields: tuple[str, str, str, str], invalid: list[str]
) -> None:
    with pytest.raises(InvalidInputError) as raised:
        Vehicle.create(*fields)

    assert [error.field for error in raised.value.errors] == invalid


@pytest.mark.parametrize("status", list(DriverStatus))
def test_the_vehicle_can_be_saved_at_any_status_without_a_new_review(
    status: DriverStatus,
) -> None:
    driver = profile(status, vehicle=status is DriverStatus.APPROVED)
    corolla = Vehicle.create("Toyota", "Corolla", "Grey", "XYZ9")

    driver.save_vehicle(corolla)

    assert driver.vehicle == corolla
    assert driver.status is status
