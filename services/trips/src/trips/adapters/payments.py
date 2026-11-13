"""HTTP adapter for the Payments microservice: the rider's price for a trip (#97, #99)."""

from typing import Literal
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from trips.domain.errors import PricingUnavailableError
from trips.domain.request_errors import CardStatusUnavailableError
from trips.domain.values import Quote


class _QuoteResponse(BaseModel):
    amount_cents: int = Field(alias="amountCents", strict=True, ge=0)
    currency: Literal["CAD"]
    explanation: str = Field(strict=True)


class HTTPPricingService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def quote(self, distance_meters: int) -> Quote:
        try:
            response = await self.client.post(
                "/internal/quotes", json={"distanceMeters": distance_meters}
            )
            response.raise_for_status()
            data = _QuoteResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            # Includes 501 while the quote endpoint isn't implemented yet (#99).
            raise PricingUnavailableError() from exc

        return Quote(
            amount_cents=data.amount_cents,
            currency=data.currency,
            explanation=data.explanation,
        )


class _CardStatusResponse(BaseModel):
    user_id: UUID = Field(alias="userId")
    has_card: bool = Field(alias="hasCard", strict=True)


class HTTPRiderCardService:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def has_card(self, rider_id: UUID) -> bool:
        try:
            response = await self.client.get(f"/internal/customers/{rider_id}/card")
            response.raise_for_status()
            data = _CardStatusResponse.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise CardStatusUnavailableError(
                "Could not check the rider's saved payment card."
            ) from exc

        if data.user_id != rider_id:
            raise CardStatusUnavailableError("Payments returned card status for a different rider.")

        return data.has_card
