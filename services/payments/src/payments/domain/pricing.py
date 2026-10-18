"""Pricing rules for a rider's share of a trip."""

RATE_CENTS_PER_KM = 45
MINIMUM_FARE_CENTS = 200
ROUNDING_INCREMENT_CENTS = 5


def calculate_quote(distance_meters: int) -> int:
    """Return the fare in cents, rounded to 5 cents, with a $2 minimum."""
    if not 0 <= distance_meters <= 200_000:
        raise ValueError("Distance must be between 0 and 200,000 metres")

    # Work in five-cent units to avoid floating-point rounding errors.
    units = (distance_meters * RATE_CENTS_PER_KM + 500 * ROUNDING_INCREMENT_CENTS) // (
        1000 * ROUNDING_INCREMENT_CENTS
    )

    return max(MINIMUM_FARE_CENTS, units * ROUNDING_INCREMENT_CENTS)
