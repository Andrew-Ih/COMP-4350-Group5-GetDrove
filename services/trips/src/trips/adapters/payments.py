"""HTTP adapter for the Payments microservice: the rider's price for a trip (#97, #99)."""

from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from trips.domain.errors import PricingUnavailableError
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
