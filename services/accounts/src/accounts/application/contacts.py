"""Use case: where to send emails (#146). Notifications asks for the name and email of the
people an event is about; event payloads carry only user IDs, so emails never travel on the
event bus."""

from collections.abc import Sequence
from uuid import UUID

from accounts.application.ports import UnitOfWork
from accounts.domain.user import User


class ListContacts:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_ids: Sequence[UUID]) -> list[User]:
        """The users with these IDs, in the order asked for. Unknown IDs are left out."""
        async with self._uow as uow:
            found = {user.id: user for user in await uow.users.get_many(user_ids)}
        return [found[user_id] for user_id in dict.fromkeys(user_ids) if user_id in found]
