"""Putting the demo drivers through the application to drive (#180), with in-memory fakes."""

import pytest

from accounts.application.seed_drivers import (
    DEMO_INSURANCE,
    DEMO_LICENCE,
    DemoDriver,
    DemoVehicle,
    SeedDrivers,
    placeholder_pdf,
)
from accounts.domain.documents import Document, DocumentKind
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.email import Email
from accounts.domain.errors import UserNotFoundError
from accounts.domain.user import User
from accounts.testing import FIXED_NOW, FakeClock, FakeDocumentStorage, FakeUnitOfWork
from events.catalog import DriverApproved

ADMIN = "getdrove.demo.admin@myumanitoba.ca"
MAYA = "getdrove.demo.maya@myumanitoba.ca"
SAM = "getdrove.demo.sam@myumanitoba.ca"
COROLLA = DemoVehicle("Toyota", "Corolla", "Blue", "GDMAYA1")
ESCAPE = DemoVehicle("Ford", "Escape", "Black", "GDSAM05")


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
def seed(uow: FakeUnitOfWork, storage: FakeDocumentStorage) -> SeedDrivers:
    return SeedDrivers(uow, storage, FakeClock())


async def account(uow: FakeUnitOfWork, email: str) -> User:
    user = User.register(Email.parse(email), "hash", "Demo", "Person")
    await uow.users.add(user)
    return user


async def profile(uow: FakeUnitOfWork, user: User) -> DriverProfile:
    found = await uow.drivers.get(user.id)
    assert found is not None
    return found


async def test_a_driver_is_given_documents_a_car_and_approved(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, seed: SeedDrivers
) -> None:
    admin, maya = await account(uow, ADMIN), await account(uow, MAYA)

    result = await seed([DemoDriver(MAYA, COROLLA)], ADMIN, make_admin=False)

    assert result.approved == [MAYA]
    done = await profile(uow, maya)
    assert done.status is DriverStatus.APPROVED
    assert done.reviewed_by == admin.id
    assert done.vehicle == Vehicle.create("Toyota", "Corolla", "Blue", "GDMAYA1")
    assert sorted(storage.files.values()) == sorted([DEMO_LICENCE, DEMO_INSURANCE])
    # As the admin page does it, so Trips hears the driver may post.
    assert uow.events.published == [DriverApproved(user_id=maya.id)]


async def test_a_pending_driver_is_left_for_the_admin(
    uow: FakeUnitOfWork, seed: SeedDrivers
) -> None:
    await account(uow, ADMIN)
    sam = await account(uow, SAM)

    result = await seed([DemoDriver(SAM, ESCAPE, approved=False)], ADMIN, make_admin=False)

    assert (result.pending, result.approved) == ([SAM], [])
    left = await profile(uow, sam)
    assert left.status is DriverStatus.PENDING
    assert left.vehicle is not None
    assert left.licence_key and left.insurance_key  # so the admin has something to open
    assert uow.events.published == []


async def test_running_it_again_approves_nobody_twice(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, seed: SeedDrivers
) -> None:
    await account(uow, ADMIN)
    await account(uow, MAYA)
    await account(uow, SAM)
    drivers = [DemoDriver(MAYA, COROLLA), DemoDriver(SAM, ESCAPE, approved=False)]
    await seed(drivers, ADMIN, make_admin=False)
    files = dict(storage.files)

    again = await seed(drivers, ADMIN, make_admin=False)

    assert again.already_approved == [MAYA]
    assert again.approved == []
    assert again.pending == [SAM]
    assert storage.files == files  # Sam's pending application isn't uploaded again
    assert len(uow.events.published) == 1


async def test_a_driver_rejected_in_a_demo_is_resubmitted_and_approved(
    uow: FakeUnitOfWork, seed: SeedDrivers
) -> None:
    admin, maya = await account(uow, ADMIN), await account(uow, MAYA)
    rejected = DriverProfile(maya.id, vehicle=Vehicle.create("Honda", "Civic", "Red", "OLD1"))
    rejected.submit_documents("old-licence", "old-insurance", FIXED_NOW)
    rejected.reject(admin.id, "Blurry photo", FIXED_NOW)
    await uow.drivers.save(rejected)

    result = await seed([DemoDriver(MAYA, COROLLA)], ADMIN, make_admin=False)

    assert result.approved == [MAYA]
    done = await profile(uow, maya)
    assert done.status is DriverStatus.APPROVED
    assert done.vehicle is not None
    assert done.vehicle.plate == "OLD1"  # a car they already saved is kept


async def test_the_demo_admin_gets_the_role_only_when_asked(
    uow: FakeUnitOfWork, seed: SeedDrivers
) -> None:
    admin = await account(uow, ADMIN)
    await account(uow, MAYA)

    without = await seed([DemoDriver(MAYA, COROLLA)], ADMIN, make_admin=False)
    assert without.admins == []
    assert not uow.users.rows[admin.id].is_admin

    with_role = await seed([DemoDriver(MAYA, COROLLA)], ADMIN, make_admin=True)
    assert with_role.admins == [ADMIN]
    assert uow.users.rows[admin.id].is_admin


async def test_a_missing_account_stops_it(uow: FakeUnitOfWork, seed: SeedDrivers) -> None:
    await account(uow, ADMIN)

    with pytest.raises(UserNotFoundError, match="run the account seed first"):
        await seed([DemoDriver(MAYA, COROLLA)], ADMIN, make_admin=False)


@pytest.mark.parametrize(
    ("kind", "pdf"),
    [(DocumentKind.LICENCE, DEMO_LICENCE), (DocumentKind.INSURANCE, DEMO_INSURANCE)],
)
def test_the_placeholders_are_pdfs_the_upload_accepts(kind: DocumentKind, pdf: bytes) -> None:
    document = Document.check(kind, pdf)

    assert document.content_type == "application/pdf"
    assert pdf.startswith(b"%PDF-1.4\n")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert b"not a real document" in pdf


def test_the_placeholder_cross_reference_points_at_each_object() -> None:
    """PDF viewers find objects through the xref table; wrong offsets show a broken file."""
    pdf = placeholder_pdf("hello")
    xref_at = int(pdf.rsplit(b"startxref\n", 1)[1].split(b"\n")[0])
    assert pdf[xref_at:].startswith(b"xref\n0 6\n")
    entries = pdf[xref_at:].split(b"\n")[3:8]
    for number, entry in enumerate(entries, start=1):
        offset = int(entry.split()[0])
        assert pdf[offset:].startswith(b"%d 0 obj" % number)
