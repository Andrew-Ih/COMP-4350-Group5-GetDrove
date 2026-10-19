"""Distance-based rider pricing.

Rate and minimum fare are supplied by configuration (ADR 0012).
"""

METERS_PER_KM = 1000
MAX_DISTANCE_METERS = 200_000
ROUNDING_INCREMENT_CENTS = 5


def calculate_quote(
    distance_meters: int,
    rate_cents_per_km: int,
    minimum_fare_cents: int,
) -> int:
    """Calculate a rider's fare in cents, rounded to 5 cents."""
    if not 0 <= distance_meters <= MAX_DISTANCE_METERS:
        raise ValueError("Distance must be between 0 and 200,000 metres")

    if rate_cents_per_km < 0 or minimum_fare_cents < 0:
        raise ValueError("Rate and minimum fare must not be negative")

    rounding_divisor = METERS_PER_KM * ROUNDING_INCREMENT_CENTS

    # Add half a rounding step so halfway cases round upward.
    rounded_units = (
        distance_meters * rate_cents_per_km + rounding_divisor // 2
    ) // rounding_divisor

    rounded_amount_cents = rounded_units * ROUNDING_INCREMENT_CENTS

    return max(minimum_fare_cents, rounded_amount_cents)
