"""Payments API (Sprint 1 contract, issue #108): price quotes.

Internal: called by Trips inside Docker (http://payments:8000/internal/quotes) to show each
search result's cost; the gateway never exposes it. Card setup and holds come in Sprint 2.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from payments.adapters.api.schemas import Problem, Quote, QuoteRequest
from payments.domain.pricing import calculate_quote

internal_router = APIRouter(prefix="/internal", tags=["internal"])


@dataclass(frozen=True)
class PricingConfig:
    rate_cents_per_km: int
    minimum_fare_cents: int


def get_pricing_config() -> PricingConfig:
    raise RuntimeError("Pricing dependency has not been configured")


INVALID: dict[int | str, dict[str, Any]] = {
    422: {
        "model": Problem,
        "description": "Invalid input; `errors` lists the fields (code `invalid_input`)",
    }
}


@internal_router.post(
    "/quotes",
    summary="Price a rider's share",
    description="The rider's estimated cost for travelling `distanceMeters` in the car: "
    "$0.45 per km, rounded to the nearest 5 cents, with a $2.00 minimum, plus a one-line "
    "explanation. The quote shown when requesting is the amount charged unless the trip "
    "changes.",
    responses=INVALID,
)
async def quote(
    body: QuoteRequest,
    config: Annotated[PricingConfig, Depends(get_pricing_config)],
) -> Quote:
    amount_cents = calculate_quote(
        distance_meters=body.distance_meters,
        rate_cents_per_km=config.rate_cents_per_km,
        minimum_fare_cents=config.minimum_fare_cents,
    )

    distance_km = round(body.distance_meters / 1000, 1)
    rate_dollars = config.rate_cents_per_km / 100
    minimum_dollars = config.minimum_fare_cents / 100

    explanation = f"{distance_km:g} km at ${rate_dollars:.2f}/km"

    if amount_cents == config.minimum_fare_cents:
        explanation += f" (${minimum_dollars:.2f} minimum)"

    return Quote(
        amount_cents=amount_cents,
        currency="CAD",
        explanation=explanation,
    )
