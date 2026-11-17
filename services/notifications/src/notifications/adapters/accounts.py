"""The real ``ContactDirectory``: Accounts' GET /internal/contacts (#146), reachable only
inside Docker (http://accounts:8000)."""

import logging
from collections.abc import Sequence
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from notifications.application.ports import ContactsUnavailableError
from notifications.domain.notification_email import Contact

logger = logging.getLogger(__name__)

# Accounts takes at most 50 IDs per request.
BATCH_SIZE = 50


class _Contact(BaseModel):
    id: UUID
    first_name: str = Field(alias="firstName")
    email: str


class _Contacts(BaseModel):
    contacts: list[_Contact]


class HTTPContactDirectory:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def contacts(self, user_ids: Sequence[UUID]) -> dict[UUID, Contact]:
        unique = list(dict.fromkeys(user_ids))
        found: dict[UUID, Contact] = {}
        for start in range(0, len(unique), BATCH_SIZE):
            batch = unique[start : start + BATCH_SIZE]
            for item in await self._fetch(batch):
                found[item.id] = Contact(first_name=item.first_name, email=item.email)
        return found

    async def _fetch(self, user_ids: list[UUID]) -> list[_Contact]:
        try:
            response = await self._client.get(
                "/internal/contacts", params={"ids": [str(user_id) for user_id in user_ids]}
            )
            response.raise_for_status()
            return _Contacts.model_validate_json(response.content).contacts
        except (httpx.HTTPError, ValidationError) as exc:
            # The response holds emails: say what went wrong, never what came back.
            logger.warning("Accounts contacts lookup failed: %s", type(exc).__name__)
            raise ContactsUnavailableError("Couldn't get contacts from Accounts") from exc
