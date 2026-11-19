"""Use case: put the demo drivers through the driving application (#180), and (locally)
make the demo admin.

Each step is the same use case a real student and admin go through: upload documents
(placeholder PDFs that say they're not real), save the vehicle, and approve. So approving
publishes DriverApproved through the outbox exactly as the admin page does, and Trips lets
the driver post (#11). A driver marked ``approved=False`` is left pending, for the admin to
review in a demo.

Running it again is safe: a driver who's already approved is left alone, a missing step is
done, and nobody is approved twice.
"""

from dataclasses import dataclass, field
from uuid import UUID

from accounts.application.admin import ApproveDriver, MakeAdmin
from accounts.application.documents import UploadDriverDocuments
from accounts.application.drivers import SaveVehicle
from accounts.application.ports import Clock, DocumentStorage, UnitOfWork
from accounts.domain.driver import DriverProfile, DriverStatus
from accounts.domain.email import Email
from accounts.domain.errors import UserNotFoundError


@dataclass(frozen=True)
class DemoVehicle:
    make: str
    model: str
    colour: str
    plate: str


@dataclass(frozen=True)
class DemoDriver:
    email: str
    vehicle: DemoVehicle
    approved: bool = True  # False: left pending, for the admin to review in a demo


@dataclass
class SeedDriversResult:
    approved: list[str] = field(default_factory=list)  # approved by this run
    pending: list[str] = field(default_factory=list)  # waiting for the admin
    already_approved: list[str] = field(default_factory=list)
    admins: list[str] = field(default_factory=list)


def placeholder_pdf(text: str) -> bytes:
    """A one-page PDF that says ``text``: what an admin opens for a demo driver. Built by
    hand (with a correct cross-reference table) so no PDF library is needed."""
    stream = f"BT /F1 16 Tf 36 60 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 144] /Contents 4 0 R"
        b" /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(pdf)


DEMO_LICENCE = placeholder_pdf("GetDrove demo licence - not a real document")
DEMO_INSURANCE = placeholder_pdf("GetDrove demo insurance - not a real document")


class SeedDrivers:
    def __init__(self, uow: UnitOfWork, storage: DocumentStorage, clock: Clock) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock

    async def __call__(
        self, drivers: list[DemoDriver], admin_email: str, *, make_admin: bool
    ) -> SeedDriversResult:
        """The accounts (drivers and admin) must exist already: SeedAccounts runs first.
        404 user_not_found otherwise.

        The demo admin account is who approves the drivers. It only gets the admin role
        with ``make_admin``: an admin can open every applicant's licence and insurance, and
        the demo password is shared, so on the live site a team member's own account is
        made admin instead (make_admin command)."""
        result = SeedDriversResult()
        admin_id = await self._user_id(admin_email)
        if make_admin:
            admin = await MakeAdmin(self._uow)(admin_email)
            result.admins.append(admin.email.value)

        for driver in drivers:
            user_id = await self._user_id(driver.email)
            profile = await self._profile(user_id)
            if profile.is_approved:
                result.already_approved.append(driver.email)
                continue
            if profile.vehicle is None:
                vehicle = driver.vehicle
                await SaveVehicle(self._uow)(
                    user_id, vehicle.make, vehicle.model, vehicle.colour, vehicle.plate
                )
            # Never applied, or rejected in an earlier demo: (re)submit, so it's pending.
            if profile.status in (DriverStatus.NONE, DriverStatus.REJECTED):
                await UploadDriverDocuments(self._uow, self._storage, self._clock)(
                    user_id, DEMO_LICENCE, DEMO_INSURANCE
                )
            if driver.approved:
                await ApproveDriver(self._uow, self._clock)(admin_id, user_id)
                result.approved.append(driver.email)
            else:
                result.pending.append(driver.email)
        return result

    async def _user_id(self, email: str) -> UUID:
        async with self._uow as uow:
            user = await uow.users.get_by_email(Email.parse(email))
        if user is None:
            raise UserNotFoundError(f"No account uses {email}: run the account seed first.")
        return user.id

    async def _profile(self, user_id: UUID) -> DriverProfile:
        async with self._uow as uow:
            return await uow.drivers.get(user_id) or DriverProfile(user_id)
