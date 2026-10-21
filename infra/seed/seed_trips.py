"""Posts the demo drivers' trips through the real API (#111), so Trips works out each route
with Routing and OSRM exactly as for a real driver.

Run it after the accounts exist (accounts.infrastructure.seed), against any running
GetDrove, with the same demo password:

    SEED_PASSWORD=... uv run python infra/seed/seed_trips.py --site http://localhost

For each driver in demo.json it logs in, looks at the trips they already have, and posts
only the commutes in the next two weeks that are missing. So running it again before a
demo fills the two weeks back up and never posts the same trip twice. Times in demo.json
are Winnipeg time; the API wants UTC.
"""

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

import httpx
from demo_data import DemoData, DemoDataError, Person, TripPlan, load_demo_data


def _winnipeg() -> ZoneInfo:
    """Winnipeg's rules from the tzdata package, not the operating system's time zone files
    (which ZoneInfo would read first), so every machine agrees. Older system files still
    move Manitoba to UTC-6 in November 2026; tzdata 2026e (package 2026.5) keeps it on UTC-5.
    """
    with files("tzdata.zoneinfo").joinpath("America").joinpath("Winnipeg").open("rb") as f:
        return ZoneInfo.from_file(f, key="America/Winnipeg")


WINNIPEG = _winnipeg()
DAYS_AHEAD = 14
WEEKDAY_NUMBERS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}


@dataclass
class DriverReport:
    name: str
    posted: int = 0
    already_there: int = 0
    error: str | None = None


@dataclass
class SeedReport:
    drivers: list[DriverReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(driver.error is None for driver in self.drivers)


def departures(plan: TripPlan, now: datetime, days: int = DAYS_AHEAD) -> list[datetime]:
    """When this commute leaves over the next ``days`` days, in UTC. Times already past are
    left out, since Trips only accepts trips in the future."""
    today = now.astimezone(WINNIPEG).date()
    wanted = {WEEKDAY_NUMBERS[day] for day in plan.weekdays}
    result = []
    for offset in range(days):
        day: date = today + timedelta(days=offset)
        if day.weekday() not in wanted:
            continue
        # Winnipeg time, so daylight saving is applied for that date.
        leaves = datetime.combine(day, plan.depart_at, tzinfo=WINNIPEG).astimezone(UTC)
        if leaves > now:
            result.append(leaves)
    return result


def seed_trips(
    client: httpx.Client, data: DemoData, password: str, now: datetime, days: int = DAYS_AHEAD
) -> SeedReport:
    """``client`` points at the site (e.g. http://localhost). One driver's failure is
    reported and the others still go ahead."""
    report = SeedReport()
    for driver in data.drivers:
        result = DriverReport(f"{driver.first_name} {driver.last_name}")
        report.drivers.append(result)
        try:
            _seed_driver(client, driver, password, now, days, result)
        except httpx.HTTPError as exc:
            result.error = f"couldn't reach the site: {exc}"
    return report


def _seed_driver(
    client: httpx.Client,
    driver: Person,
    password: str,
    now: datetime,
    days: int,
    result: DriverReport,
) -> None:
    login = client.post(
        "/api/accounts/auth/login", json={"email": driver.email, "password": password}
    )
    if login.status_code != 200:
        result.error = f"couldn't log in ({_problem(login)}); run the accounts seed first?"
        return
    auth = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    mine = client.get("/api/trips/mine", params={"role": "driver"}, headers=auth)
    if mine.status_code != 200:
        result.error = f"couldn't list their trips ({_problem(mine)})"
        return
    # What they already have, by direction and departure time, so only the gaps get posted.
    existing = {
        (trip["direction"], datetime.fromisoformat(trip["departureAt"])) for trip in mine.json()
    }

    for plan in driver.trips:
        for leaves in departures(plan, now, days):
            if (plan.direction, leaves) in existing:
                result.already_there += 1
                continue
            posted = client.post(
                "/api/trips/",
                headers=auth,
                json={
                    "direction": plan.direction,
                    "place": {
                        "label": driver.home.label,
                        "lat": driver.home.lat,
                        "lng": driver.home.lng,
                    },
                    "departureAt": leaves.isoformat().replace("+00:00", "Z"),
                    "seatsTotal": plan.seats,
                },
            )
            if posted.status_code != 201:
                result.error = f"a trip was refused ({_problem(posted)})"
                return
            result.posted += 1


def _problem(response: httpx.Response) -> str:
    """The API's error code (Problem Details), or just the status."""
    try:
        code = response.json().get("code")
    except ValueError:
        code = None
    return f"{response.status_code} {code}" if code else str(response.status_code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post the demo drivers' trips (#111).")
    parser.add_argument("--site", default="http://localhost", help="the gateway's address")
    parser.add_argument("--days", type=int, default=DAYS_AHEAD, help="how many days ahead")
    args = parser.parse_args(argv)

    password = os.environ.get("SEED_PASSWORD", "")
    if not password:
        print("Set SEED_PASSWORD to the demo accounts' password.", file=sys.stderr)
        return 2
    try:
        data = load_demo_data()
    except DemoDataError as exc:
        print(exc, file=sys.stderr)
        return 1

    with httpx.Client(base_url=args.site, timeout=30) as client:
        report = seed_trips(client, data, password, datetime.now(UTC), args.days)

    for driver in report.drivers:
        if driver.error:
            print(f"FAILED   {driver.name}: {driver.error}")
        else:
            print(
                f"posted   {driver.name}: {driver.posted} new trips, "
                f"{driver.already_there} already there"
            )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
