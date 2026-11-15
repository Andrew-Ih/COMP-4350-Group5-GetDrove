"""Admin use cases (#127): reviewing applications to drive, and making an admin.

Approving or rejecting publishes DriverApproved or DriverRejected through the outbox, in
the same transaction as the decision. Trips uses them to allow posting (#11) and
Notifications to tell the driver (#146).
"""

from dataclasses import dataclass
from uuid import UUID

from accounts.application.ports import Clock, UnitOfWork
from accounts.domain.driver import DriverProfile, DriverStatus
from accounts.domain.email import Email
from accounts.domain.errors import DriverNotFoundError, UserNotFoundError
from accounts.domain.user import User
from events.catalog import DriverApproved, DriverRejected


@dataclass(frozen=True)
class Application:
    """A driver's application with the account it belongs to."""

    profile: DriverProfile
    user: User


class ListDriverApplications:
    """GET /admin/drivers?status=...: applications with that status, oldest first."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, status: DriverStatus) -> list[Application]:
        async with self._uow as uow:
            applications = []
            for profile in await uow.drivers.list_by_status(status):
                user = await uow.users.get(profile.user_id)
                if user is not None:  # always, since a deleted user's profile goes too
                    applications.append(Application(profile, user))
            return applications


class ApproveDriver:
    """POST /admin/drivers/{userId}/approve. 404 driver_not_found if they never applied;
    409 driver_not_pending or vehicle_missing. Publishes DriverApproved."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, admin_id: UUID, user_id: UUID) -> Application:
        async with self._uow as uow:
            profile, user = await _application(uow, user_id)
            profile.approve(admin_id, self._clock.now())
            await uow.drivers.save(profile)
            await uow.events.publish(DriverApproved(user_id=user_id))
            await uow.commit()
        return Application(profile, user)


class RejectDriver:
    """POST /admin/drivers/{userId}/reject with a reason the driver sees. 404
    driver_not_found if they never applied; 409 driver_not_pending. Publishes
    DriverRejected."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def __call__(self, admin_id: UUID, user_id: UUID, reason: str) -> Application:
        async with self._uow as uow:
            profile, user = await _application(uow, user_id)
            profile.reject(admin_id, reason, self._clock.now())  # trims the reason
            await uow.drivers.save(profile)
            await uow.events.publish(DriverRejected(user_id=user_id, reason=reason.strip()))
            await uow.commit()
        return Application(profile, user)


async def _application(uow: UnitOfWork, user_id: UUID) -> tuple[DriverProfile, User]:
    # Locked, so two admins deciding at once can't both succeed: the second sees the first
    # one's decision and gets 409.
    profile = await uow.drivers.get(user_id, for_update=True)
    user = await uow.users.get(user_id) if profile else None
    # A student who only saved a vehicle has a profile, but hasn't applied.
    if profile is None or profile.status is DriverStatus.NONE or user is None:
        raise DriverNotFoundError("This student hasn't applied to drive.")
    return profile, user


class MakeAdmin:
    """Gives an existing account the admin role (#127), for the one-off make_admin command.
    It takes effect at their next login or token refresh. 404 user_not_found."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, email: str) -> User:
        parsed = Email.parse(email)
        async with self._uow as uow:
            user = await uow.users.get_by_email(parsed)
            if user is None:
                raise UserNotFoundError(f"No account uses {parsed.value}.")
            if not user.is_admin:
                user.is_admin = True
                await uow.users.save(user)
                await uow.commit()
            return user
