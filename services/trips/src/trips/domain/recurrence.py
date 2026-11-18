"""Expand recurring trip schedules into individual departure times."""

from datetime import UTC, datetime, timedelta

from trips.domain.entities import WEEKDAY_NUMBERS, WINNIPEG_TZ, TripSeries


def expand_trip_series(series: TripSeries) -> list[datetime]:
    """Return each matching departure as a UTC datetime.

    Recurrence is calculated using Winnipeg local calendar dates
    and wall-clock time, preserving departure time across timezone
    offset changes.
    """
    first_local = series.departure_at.astimezone(WINNIPEG_TZ)
    departure_time = first_local.time().replace(tzinfo=None)

    selected_weekdays = {WEEKDAY_NUMBERS[day] for day in series.weekdays}

    current_date = first_local.date()
    departures = []

    while current_date <= series.end_date:
        if current_date.weekday() in selected_weekdays:
            local_departure = datetime.combine(
                current_date,
                departure_time,
                tzinfo=WINNIPEG_TZ,
            )

            departures.append(local_departure.astimezone(UTC))

        current_date += timedelta(days=1)

    return departures
