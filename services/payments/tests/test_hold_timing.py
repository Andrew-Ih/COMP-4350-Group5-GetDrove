"""Six-day scheduling boundary, independent of Docker and wall-clock time."""

from datetime import UTC, datetime, timedelta

import pytest

from payments.domain.holds import authorization_time


@pytest.mark.parametrize(
    ("lead", "expected_delay"),
    [
        (timedelta(hours=12), timedelta(0)),
        (timedelta(days=6), timedelta(0)),
        (timedelta(days=6, microseconds=1), timedelta(days=5, microseconds=1)),
        (timedelta(days=14), timedelta(days=13)),
    ],
)
def test_when_to_authorize_a_saved_share(lead, expected_delay):
    accepted_at = datetime(2030, 1, 1, tzinfo=UTC)
    assert authorization_time(accepted_at, accepted_at + lead) == accepted_at + expected_delay
