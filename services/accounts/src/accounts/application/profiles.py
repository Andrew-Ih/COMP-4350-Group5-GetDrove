"""Use cases for looking up other users (#143): the public profile any student can see,
and the batch lookup Trips uses for a driver's requests and auto-accept."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from accounts.application.ports import UnitOfWork
from accounts.domain.driver import Vehicle
from accounts.domain.errors import UserNotFoundError
from accounts.domain.reputation import Reputation
from accounts.domain.user import User


@dataclass(frozen=True)
class UserSummary:
    """What other people may know about a user. The API decides how much of it to show:
    the public profile drops the plate; Trips gets it, for riders accepted on a trip."""

    user: User
    reputation: Reputation
    is_driver: bool  # an approved driver
    vehicle: Vehicle | None  # approved drivers only


class GetPublicProfile:
    """GET /users/{id}/profile: 404 user_not_found for an unknown ID."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> UserSummary:
        async with self._uow as uow:
            found = await _summaries(uow, [user_id])
        if not found:
            raise UserNotFoundError("There's no user with this ID.")
        return found[0]


class LookUpUsers:
    """GET /internal/users (for Trips): many users in one call, in the order asked, each
    once. Unknown IDs are left out."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_ids: Sequence[UUID]) -> list[UserSummary]:
        async with self._uow as uow:
            return await _summaries(uow, user_ids)


async def _summaries(uow: UnitOfWork, user_ids: Sequence[UUID]) -> list[UserSummary]:
    # One query per table, however many users, so a list of 20 riders isn't 20 queries.
    wanted = list(dict.fromkeys(user_ids))  # keeps the order, drops repeats
    users = await uow.users.get_many(wanted)
    drivers = await uow.drivers.get_many(users.keys())
    reputations = await uow.reputation.get_many(users.keys())

    summaries = []
    for user_id in wanted:
        user = users.get(user_id)
        if user is None:
            continue
        profile = drivers.get(user_id)
        is_driver = profile is not None and profile.is_approved
        summaries.append(
            UserSummary(
                user=user,
                reputation=reputations.get(user_id) or Reputation(user_id),
                is_driver=is_driver,
                # A pending or rejected student's car isn't shown: they aren't driving.
                vehicle=profile.vehicle if profile is not None and is_driver else None,
            )
        )
    return summaries
