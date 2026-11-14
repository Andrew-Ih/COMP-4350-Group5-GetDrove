"""HTTP adapter for the Accounts microservice: riders' names, ratings and no-shows (#143)."""

from collections.abc import Sequence
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from trips.application.ports import RiderProfile
from trips.domain.request_errors import AccountsUnavailableError

# Accounts accepts 1 to 50 ids per call.
BATCH_SIZE = 50


class _User(BaseModel):
    id: UUID
    first_name: str = Field(alias="firstName", strict=True)
    rating: float | None = Field(ge=1, le=5)
    rating_count: int = Field(alias="ratingCount", strict=True, ge=0)
    no_show_count: int = Field(alias="noShowCount", strict=True, ge=0)


class _UsersResponse(BaseModel):
    users: list[_User]


class HTTPRiderProfileService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get_many(self, rider_ids: Sequence[UUID]) -> dict[UUID, RiderProfile]:
        unique = list(dict.fromkeys(rider_ids))
        profiles: dict[UUID, RiderProfile] = {}

        for start in range(0, len(unique), BATCH_SIZE):
            batch = unique[start : start + BATCH_SIZE]
            wanted = set(batch)
            try:
                response = await self.client.get(
                    "/internal/users", params={"ids": [str(rider_id) for rider_id in batch]}
                )
                if response.status_code != 200:
                    raise AccountsUnavailableError("Accounts did not return the riders.")
                data = _UsersResponse.model_validate_json(response.content)
            except (httpx.HTTPError, ValidationError) as exc:
                raise AccountsUnavailableError(
                    "Could not load the riders' names and ratings."
                ) from exc

            for user in data.users:
                if user.id in wanted:
                    profiles[user.id] = RiderProfile(
                        id=user.id,
                        first_name=user.first_name,
                        rating=user.rating,
                        rating_count=user.rating_count,
                        no_show_count=user.no_show_count,
                    )

        return profiles
