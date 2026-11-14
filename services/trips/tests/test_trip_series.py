
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from trips.domain.entities import TripSeries
from trips.domain.values import Direction, Location

WINNIPEG = ZoneInfo("America/Winnipeg")


@pytest.fixture
def valid_series_data():
    return {
        "driver_id": uuid4(),
        "direction": Direction.TO_CAMPUS,
        "place": Location(
            label="Pembina Highway",
            lat=49.82,
            lng=-97.15,
        ),
        "departure_at": datetime(
            2026, 11, 16, 8, 0,
            tzinfo=WINNIPEG,
        ),
        "seats_total": 3,
        "weekdays": ["mon", "wed", "fri"],
        "end_date": date(2026, 12, 11),
    }


def test_create_valid_trip_series(valid_series_data):
    series = TripSeries.create(**valid_series_data)

    assert series.id is not None
    assert series.driver_id == valid_series_data["driver_id"]
    assert series.weekdays == ("mon", "wed", "fri")
    assert series.seats_total == 3
    assert series.end_date == date(2026, 12, 11)


def test_reject_empty_weekdays(valid_series_data):
    valid_series_data["weekdays"] = []

    with pytest.raises(ValueError, match="At least one weekday"):
        TripSeries.create(**valid_series_data)


def test_reject_duplicate_weekdays(valid_series_data):
    valid_series_data["weekdays"] = ["mon", "mon"]

    with pytest.raises(ValueError, match="duplicates"):
        TripSeries.create(**valid_series_data)


def test_reject_weekend(valid_series_data):
    valid_series_data["weekdays"] = ["mon", "sat"]

    with pytest.raises(ValueError, match="Monday through Friday"):
        TripSeries.create(**valid_series_data)


def test_reject_end_date_before_departure(valid_series_data):
    valid_series_data["end_date"] = date(2026, 11, 15)

    with pytest.raises(ValueError, match="after first departure"):
        TripSeries.create(**valid_series_data)


def test_reject_end_date_equal_to_departure(valid_series_data):
    valid_series_data["end_date"] = date(2026, 11, 16)

    with pytest.raises(ValueError, match="after first departure"):
        TripSeries.create(**valid_series_data)


def test_reject_end_date_over_16_weeks(valid_series_data):
    valid_series_data["end_date"] = date(2027, 3, 9)

    with pytest.raises(ValueError, match="16 weeks"):
        TripSeries.create(**valid_series_data)


def test_allow_end_date_at_16_weeks(valid_series_data):
    valid_series_data["end_date"] = date(2027, 3, 8)

    series = TripSeries.create(**valid_series_data)

    assert series.end_date == date(2027, 3, 8)


@pytest.mark.parametrize("seats", [0, -1, 7])
def test_reject_invalid_seats(valid_series_data, seats):
    valid_series_data["seats_total"] = seats

    with pytest.raises(ValueError, match="Seats must be between"):
        TripSeries.create(**valid_series_data)


def test_reject_naive_departure(valid_series_data):
    valid_series_data["departure_at"] = datetime(
        2026, 11, 16, 8, 0
    )

    with pytest.raises(ValueError, match="timezone"):
        TripSeries.create(**valid_series_data)
