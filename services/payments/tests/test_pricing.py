"""Tests for distance-based rider pricing."""

import pytest

from payments.domain.pricing import calculate_rider_share


@pytest.mark.parametrize(
    ("distance_meters", "expected_cents"),
    [
        (0, 200),
        (1000, 200),
        (4000, 200),
        (4499, 200),
        (4500, 205),
        (4600, 205),
        (4700, 210),
        (9300, 420),
        (10_000, 450),
        (200_000, 9000),
    ],
)
def test_calculate_rider_share(
    distance_meters: int,
    expected_cents: int,
) -> None:
    assert calculate_rider_share(distance_meters) == expected_cents


def test_negative_distance_is_rejected() -> None:
    with pytest.raises(ValueError, match="Distance must not be negative"):
        calculate_rider_share(-1)
