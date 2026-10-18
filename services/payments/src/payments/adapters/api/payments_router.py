"""Payments API (Sprint 1 contract, issue #108): price quotes.

Internal: called by Trips inside Docker (http://payments:8000/internal/quotes) to show each
search result's cost; the gateway never exposes it. Card setup and holds come in Sprint 2.
"""

from typing import Any

from fastapi import APIRouter

from payments.adapters.api.schemas import Problem, Quote, QuoteRequest
from payments.domain.pricing import calculate_quote

internal_router = APIRouter(prefix="/internal", tags=["internal"])


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
async def quote(body: QuoteRequest) -> Quote:
    amount_cents = calculate_quote(body.distance_meters)
    distance_km = body.distance_meters / 1000

    return Quote(
        amount_cents=amount_cents,
        currency="CAD",
        explanation=f"{distance_km:g} km at $0.45/km",
    )
