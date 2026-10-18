"""Distance-based rider pricing.

Rate: CAD $0.45/km.
Round to the nearest 5 cents, with halfway cases rounded upward.
Minimum charge: CAD $2.00.
"""

CENTS_PER_KILOMETRE = 45
METRES_PER_KILOMETRE = 1000
ROUNDING_INCREMENT_CENTS = 5
MINIMUM_AMOUNT_CENTS = 200


def calculate_rider_share(distance_meters: int) -> int:
    """Return the rider's charge in CAD cents."""
    if distance_meters < 0:
        raise ValueError("Distance must not be negative.")

    rounding_divisor = METRES_PER_KILOMETRE * ROUNDING_INCREMENT_CENTS

    rounded_amount_cents = (
        (distance_meters * CENTS_PER_KILOMETRE + rounding_divisor // 2)
        // rounding_divisor
    ) * ROUNDING_INCREMENT_CENTS

    return max(MINIMUM_AMOUNT_CENTS, rounded_amount_cents)
