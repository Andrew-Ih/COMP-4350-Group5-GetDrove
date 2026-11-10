"""Payments API: price quotes (Sprint 1 contract, #108) and saved cards (Sprint 2, #262).

Internal endpoints are called inside Docker (http://payments:8000/internal/...); the gateway
never exposes them. Card endpoints are public (/api/payments/...) and return 501 until #151
implements them. Holds and releases have no endpoints: they react to Trips' events.
"""

from dataclasses import dataclass
from typing import Annotated, Any, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from common_security.dependencies import AuthenticatedUser
from payments.adapters.api.schemas import (
    CardStatus,
    PaymentMethod,
    Problem,
    Quote,
    QuoteRequest,
    SetupIntent,
)
from payments.domain.pricing import calculate_quote

internal_router = APIRouter(prefix="/internal", tags=["internal"])
cards_router = APIRouter(tags=["cards"])


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


# ---------------------------------------------------------------- saved cards (#151)


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#262).")


CARD_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _problem("Missing or invalid access token", "unauthorized"),
    503: _problem("Stripe can't be reached right now", "payments_unavailable"),
}


@cards_router.post(
    "/setup-intent",
    status_code=201,
    summary="Start adding a card",
    description="Creates a Stripe SetupIntent for the logged-in rider (and their Stripe "
    "customer, the first time). The frontend passes `clientSecret` to Stripe Elements.",
    responses=CARD_ERRORS,
)
async def create_setup_intent(user: AuthenticatedUser) -> SetupIntent:
    _not_implemented()


@cards_router.get(
    "/methods",
    summary="My saved cards",
    description="Brand, last 4 digits and expiry only. An empty list means no card yet.",
    responses=CARD_ERRORS,
)
async def payment_methods(user: AuthenticatedUser) -> list[PaymentMethod]:
    _not_implemented()


@internal_router.get(
    "/customers/{user_id}/card",
    summary="Does this rider have a card?",
    description="For Trips: a rider needs a saved card before requesting a seat.",
    responses=INVALID,
)
async def card_status(user_id: UUID) -> CardStatus:
    _not_implemented()
