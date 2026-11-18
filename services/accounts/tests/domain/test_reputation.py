"""A student's reputation (#143): the average rating is worked out from the sum and count."""

from uuid import uuid4

import pytest

from accounts.domain.reputation import Reputation


def test_everyone_starts_at_zero_with_no_rating_yet() -> None:
    reputation = Reputation(uuid4())

    assert reputation.rating is None
    assert (reputation.rating_count, reputation.trip_count, reputation.no_show_count) == (0, 0, 0)


@pytest.mark.parametrize(
    ("rating_sum", "rating_count", "average"),
    [(5, 1, 5.0), (9, 2, 4.5), (14, 3, 4.67), (3, 3, 1.0)],
)
def test_the_rating_is_the_average_to_two_decimals(
    rating_sum: int, rating_count: int, average: float
) -> None:
    reputation = Reputation(uuid4(), rating_sum=rating_sum, rating_count=rating_count)

    assert reputation.rating == average
