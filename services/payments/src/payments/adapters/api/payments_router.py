"""Payments API: distance-based rider price quotes.

Called internally by Trips at /internal/quotes.
Card setup and payment holds are handled separately.
"""

from typing import Any

from fastapi import APIRouter

from payments.adapters.api.schemas import Problem, Quote, QuoteRequest
from payments.domain.pricing import calculate_rider_share

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
    amount_cents = calculate_rider_share(body.distance_meters)
    distance_km = body.distance_meters / 1000

    return Quote(
        amount_cents=amount_cents,
        currency="CAD",
        explanation=(
            f"{distance_km:g} km at $0.45/km, rounded to the nearest $0.05 with a $2.00 minimum."
        ),
    )
