"""Payments API (Sprint 1 contract, issue #108): price quotes.

Internal: called by Trips inside Docker (http://payments:8000/internal/quotes) to show each
search result's cost; the gateway never exposes it. Card setup and holds come in Sprint 2.
The handler returns 501 Not Implemented until the real code lands (#99).
"""

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException

from payments.adapters.api.schemas import Problem, Quote, QuoteRequest

internal_router = APIRouter(prefix="/internal", tags=["internal"])


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#108).")


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
    _not_implemented()
