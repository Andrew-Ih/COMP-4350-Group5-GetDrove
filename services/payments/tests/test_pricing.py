"""Unit tests for Payments quote calculation."""

import pytest

from payments.domain.pricing import calculate_quote


@pytest.mark.parametrize(
    ("distance_meters", "expected_cents"),
    [
        (0, 200),
        (1000, 200),
        (4499, 200),
        (4500, 205),
        (4555, 205),
        (4611, 205),
        (4612, 210),
        (5000, 225),
        (6000, 270),
        (9300, 420),
        (10_000, 450),
        (200_000, 9000),
    ],
)
def test_calculate_quote(
    distance_meters: int,
    expected_cents: int,
) -> None:
    assert (
        calculate_quote(
            distance_meters=distance_meters,
            rate_cents_per_km=45,
            minimum_fare_cents=200,
        )
        == expected_cents
    )


@pytest.mark.parametrize("distance_meters", [-1, 200_001])
def test_invalid_distance(distance_meters: int) -> None:
    with pytest.raises(ValueError):
        calculate_quote(
            distance_meters=distance_meters,
            rate_cents_per_km=45,
            minimum_fare_cents=200,
        )


def test_custom_rate_changes_quote() -> None:
    assert calculate_quote(6000, 50, 200) == 300


def test_custom_minimum_fare() -> None:
    assert calculate_quote(1000, 45, 300) == 300
