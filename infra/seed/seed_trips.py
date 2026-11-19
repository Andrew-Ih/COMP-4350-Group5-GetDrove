"""Fills the demo through the real API (#111, #180): the riders' test cards, the drivers'
trips (single ones and one recurring series), and a few seat requests, some accepted.

Everything goes through the gateway as a real student would, so Trips works out routes
with Routing and OSRM, Payments saves cards with Stripe, and accepting a request places
a real test-mode hold. Run it after the accounts part (accounts.infrastructure.seed),
against any running GetDrove, with the same demo password:

    SEED_PASSWORD=... STRIPE_PUBLISHABLE_KEY=pk_test_... \\
        uv run python infra/seed/seed_trips.py --site http://localhost

Without STRIPE_PUBLISHABLE_KEY, cards and requests are skipped (a rider needs a card to ask
for a seat); trips are still posted.

Running it again is safe: a rider who has a card keeps it, only the missing commutes of
the next two weeks are posted, a series is posted once, and a request that's already
there is left alone (or accepted, if it should be). Times in demo.json are Winnipeg time;
the API wants UTC.
"""

import argparse
import os
import sys
import time as clock
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from demo_data import DemoData, DemoDataError, Person, SeatRequestPlan, TripPlan, load_demo_data


def _winnipeg() -> ZoneInfo:
    """Winnipeg's rules from the tzdata package, not the operating system's time zone files
    (which ZoneInfo would read first), so every machine agrees. Older system files still
    move Manitoba to UTC-6 in November 2026; tzdata 2026e (package 2026.5) keeps it on UTC-5.
    """
    with files("tzdata.zoneinfo").joinpath("America").joinpath("Winnipeg").open("rb") as f:
        return ZoneInfo.from_file(f, key="America/Winnipeg")


WINNIPEG = _winnipeg()
DAYS_AHEAD = 14
SERIES_DAYS = 28  # a recurring series runs four weeks from its first trip
WEEKDAY_NUMBERS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
# A request goes on a trip leaving at least this long from now, so it's not about to start.
REQUEST_LEAD = timedelta(hours=2)
# Accounts tells Trips a driver is approved through an event (DriverApproved); when Trips
# hasn't heard yet, wait and try again.
EVENT_TRIES, EVENT_WAIT_SECONDS = 15, 2.0
# Stripe's test Visa (4242 4242 4242 4242), as the card form would send it.
TEST_CARD = "pm_card_visa"

Wait = Callable[[float], None]


@dataclass
class DriverReport:
    name: str
    posted: int = 0
    already_there: int = 0
    series: int = 0  # recurring series posted by this run
    error: str | None = None


@dataclass
class CardReport:
    name: str
    saved: bool = False  # by this run; False with no error means it already had one
    error: str | None = None


@dataclass
class RequestReport:
    name: str  # "Priya Sharma → Maya Chen (to campus)"
    status: str | None = None  # where the request ended up
    created: bool = False
    error: str | None = None


@dataclass
class SeedReport:
    drivers: list[DriverReport] = field(default_factory=list)
    cards: list[CardReport] = field(default_factory=list)
    requests: list[RequestReport] = field(default_factory=list)
    skipped_payments: bool = False  # no Stripe key: no cards, so no requests either

    @property
    def ok(self) -> bool:
        reports: list[Any] = [*self.drivers, *self.cards, *self.requests]
        return all(report.error is None for report in reports)


class SeedError(Exception):
    """A step failed; the message says which and the API's code."""


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
    client: httpx.Client,
    data: DemoData,
    password: str,
    now: datetime,
    days: int = DAYS_AHEAD,
    *,
    stripe: httpx.Client | None = None,
    wait: Wait = clock.sleep,
) -> SeedReport:
    """``client`` points at the site (e.g. http://localhost); ``stripe`` at Stripe's API
    with the publishable test key, or None to skip cards and requests. One failure is
    reported and the rest still goes ahead."""
    report = SeedReport()
    logins = _Logins(client, password)

    if stripe is None:
        report.skipped_payments = any(rider.card for rider in data.riders)
    else:
        for rider in data.riders:
            if rider.card:
                card = CardReport(_name(rider))
                report.cards.append(card)
                with _reported(card):
                    _seed_card(client, stripe, logins, rider, card)

    for driver in data.drivers:
        if not driver.approved:
            continue  # pending: waits for the admin, can't post
        result = DriverReport(_name(driver))
        report.drivers.append(result)
        with _reported(result):
            _seed_driver(client, logins, driver, now, days, result, wait)

    if stripe is not None:
        for plan in data.requests:
            rider, driver = data.person(plan.rider), data.person(plan.driver)
            way = plan.direction.replace("_", " ")
            request = RequestReport(f"{_name(rider)} → {_name(driver)} ({way})")
            report.requests.append(request)
            with _reported(request):
                _seed_request(client, logins, plan, rider, driver, now, request)
    return report


@contextmanager
def _reported(report: DriverReport | CardReport | RequestReport) -> Iterator[None]:
    """A failed step is written on its report, and the seed carries on."""
    try:
        yield
    except SeedError as exc:
        report.error = str(exc)
    except httpx.HTTPError as exc:
        report.error = f"couldn't reach the site: {exc}"


class _Logins:
    """Logs each person in once."""

    def __init__(self, client: httpx.Client, password: str) -> None:
        self._client = client
        self._password = password
        self._headers: dict[str, dict[str, str]] = {}

    def headers(self, email: str) -> dict[str, str]:
        if email not in self._headers:
            login = self._client.post(
                "/api/accounts/auth/login", json={"email": email, "password": self._password}
            )
            if login.status_code != 200:
                raise SeedError(
                    f"couldn't log in ({_problem(login)}); run the accounts seed first?"
                )
            self._headers[email] = {"Authorization": f"Bearer {login.json()['accessToken']}"}
        return self._headers[email]


# ---------------------------------------------------------------- cards


def _seed_card(
    client: httpx.Client, stripe: httpx.Client, logins: _Logins, rider: Person, result: CardReport
) -> None:
    """Stripe's test Visa, saved the way the card form saves it: Payments makes a
    SetupIntent and the browser (here, this script) confirms it with Stripe."""
    auth = logins.headers(rider.email)
    methods = client.get("/api/payments/methods", headers=auth)
    if methods.status_code != 200:
        raise SeedError(f"couldn't list their cards ({_problem(methods)})")
    if methods.json():
        return  # already has a card
    setup = client.post("/api/payments/setup-intent", headers=auth)
    if setup.status_code != 201:
        raise SeedError(f"couldn't start saving a card ({_problem(setup)})")
    secret = setup.json()["clientSecret"]
    confirmed = stripe.post(
        f"/v1/setup_intents/{secret.split('_secret_')[0]}/confirm",
        data={"client_secret": secret, "payment_method": TEST_CARD},
    )
    if confirmed.status_code != 200 or confirmed.json().get("status") != "succeeded":
        raise SeedError(f"Stripe didn't save the test card ({_stripe_problem(confirmed)})")
    result.saved = True


# ---------------------------------------------------------------- trips


def _seed_driver(
    client: httpx.Client,
    logins: _Logins,
    driver: Person,
    now: datetime,
    days: int,
    result: DriverReport,
    wait: Wait,
) -> None:
    auth = logins.headers(driver.email)
    mine = client.get("/api/trips/mine", params={"role": "driver"}, headers=auth)
    if mine.status_code != 200:
        raise SeedError(f"couldn't list their trips ({_problem(mine)})")
    # Cancelled trips don't count: after a demo cancels a trip or a whole series, running
    # the seed again puts them back. (Trips' own clash check ignores cancelled trips too.)
    trips = [trip for trip in mine.json() if trip["status"] != "cancelled"]
    # What they already have, by direction and departure time, so only the gaps get posted.
    existing = {(trip["direction"], datetime.fromisoformat(trip["departureAt"])) for trip in trips}
    place = {"label": driver.home.label, "lat": driver.home.lat, "lng": driver.home.lng}

    for plan in driver.trips:
        if plan.repeat:
            _seed_series(client, auth, plan, place, trips, now, days, result, wait)
            continue
        for leaves in departures(plan, now, days):
            if (plan.direction, leaves) in existing:
                result.already_there += 1
                continue
            body = {
                "direction": plan.direction,
                "place": place,
                "departureAt": _utc(leaves),
                "seatsTotal": plan.seats,
            }
            posted = _post_waiting(client, "/api/trips/", auth, body, wait)
            if posted.status_code != 201:
                raise SeedError(f"a trip was refused ({_problem(posted)})")
            result.posted += 1


def _seed_series(
    client: httpx.Client,
    auth: dict[str, str],
    plan: TripPlan,
    place: dict[str, Any],
    trips: list[dict[str, Any]],
    now: datetime,
    days: int,
    result: DriverReport,
    wait: Wait,
) -> None:
    """One recurring series (#15) for this commute, four weeks long. Posted once: while the
    driver has an upcoming trip from a series that way that isn't cancelled, nothing more is
    posted. ``trips`` has no cancelled trips, so a cancelled series is posted again."""
    in_series = [t for t in trips if t.get("seriesId") and t["direction"] == plan.direction]
    if in_series:
        result.already_there += len(in_series)
        return
    leaving = departures(plan, now, days)
    if not leaving:
        return
    first = leaving[0]
    body = {
        "direction": plan.direction,
        "place": place,
        "departureAt": _utc(first),
        "seatsTotal": plan.seats,
        "weekdays": list(plan.weekdays),
        "endDate": (
            first.astimezone(WINNIPEG).date() + timedelta(days=SERIES_DAYS - 1)
        ).isoformat(),
    }
    posted = _post_waiting(client, "/api/trips/series", auth, body, wait)
    if posted.status_code != 201:
        raise SeedError(f"the recurring series was refused ({_problem(posted)})")
    result.posted += len(posted.json()["trips"])
    result.series += 1


def _post_waiting(
    client: httpx.Client,
    path: str,
    auth: dict[str, str],
    body: dict[str, Any],
    wait: Wait,
) -> httpx.Response:
    """Posts, trying again while Trips hasn't heard yet that the driver is approved: the
    accounts seed approves them, and DriverApproved takes a moment to reach Trips."""
    for _ in range(EVENT_TRIES - 1):
        response = client.post(path, headers=auth, json=body)
        if (response.status_code, _code(response)) != (403, "driver_not_approved"):
            return response
        wait(EVENT_WAIT_SECONDS)
    return client.post(path, headers=auth, json=body)


# ---------------------------------------------------------------- requests


def _seed_request(
    client: httpx.Client,
    logins: _Logins,
    plan: SeatRequestPlan,
    rider: Person,
    driver: Person,
    now: datetime,
    result: RequestReport,
) -> None:
    """The rider asks for a seat on the driver's next trip that way, from their home, at
    the best pickup point; the driver then accepts it if demo.json says so."""
    driver_auth = logins.headers(driver.email)
    rider_auth = logins.headers(rider.email)

    mine = client.get("/api/trips/mine", params={"role": "driver"}, headers=driver_auth)
    if mine.status_code != 200:
        raise SeedError(f"couldn't list the driver's trips ({_problem(mine)})")
    that_way = [t for t in mine.json() if t["direction"] == plan.direction]
    driver_trips = {t["id"] for t in that_way}

    asked = client.get("/api/trips/requests/mine", headers=rider_auth)
    if asked.status_code != 200:
        raise SeedError(f"couldn't list the rider's requests ({_problem(asked)})")
    request = next(
        (
            item["request"]
            for item in asked.json()
            if item["trip"]["id"] in driver_trips
            and item["request"]["status"] in ("pending", "accepted")
        ),
        None,
    )

    if request is None:
        bookable = sorted(
            (
                t
                for t in that_way
                if t["status"] == "scheduled"
                and datetime.fromisoformat(t["departureAt"]) > now + REQUEST_LEAD
            ),
            key=lambda t: t["departureAt"],
        )
        if not bookable:
            raise SeedError("the driver has no upcoming trip that way; seed the trips first")
        trip_id = bookable[0]["id"]
        home = {"lat": rider.home.lat, "lng": rider.home.lng}
        detail = client.get(f"/api/trips/{trip_id}", params=home, headers=rider_auth)
        if detail.status_code != 200:
            raise SeedError(f"couldn't open the trip ({_problem(detail)})")
        pickups = detail.json()["pickups"]
        if not pickups:
            raise SeedError("the trip doesn't pass within walking distance of the rider")
        asked_now = client.post(
            f"/api/trips/{trip_id}/requests",
            headers=rider_auth,
            json={**home, "pickupId": pickups[0]["id"]},
        )
        if asked_now.status_code != 201:
            raise SeedError(f"the request was refused ({_problem(asked_now)})")
        request = asked_now.json()
        result.created = True

    if plan.status == "accepted" and request["status"] == "pending":
        accepted = client.post(f"/api/trips/requests/{request['id']}/accept", headers=driver_auth)
        if accepted.status_code != 200:
            raise SeedError(f"the driver couldn't accept it ({_problem(accepted)})")
        result.status = "accepted"
    else:
        result.status = request["status"]


# ---------------------------------------------------------------- helpers


def _name(person: Person) -> str:
    return f"{person.first_name} {person.last_name}"


def _utc(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body.get("code") if isinstance(body, dict) else None


def _problem(response: httpx.Response) -> str:
    """The API's error code (Problem Details), or just the status."""
    code = _code(response)
    return f"{response.status_code} {code}" if code else str(response.status_code)


def _stripe_problem(response: httpx.Response) -> str:
    """Stripe's error code, or the SetupIntent's status when it didn't succeed."""
    try:
        body = response.json()
    except ValueError:
        return str(response.status_code)
    error = body.get("error") or {}
    code = error.get("code") or error.get("type") or body.get("status") or ""
    return f"{response.status_code} {code}".strip()


def stripe_client(publishable_key: str) -> httpx.Client:
    """Stripe's API as the browser calls it: with the publishable test key, which can only
    confirm a SetupIntent it was given the client secret for."""
    if not publishable_key.startswith("pk_test_"):
        raise ValueError("STRIPE_PUBLISHABLE_KEY must be a test key (pk_test_...)")
    return httpx.Client(base_url="https://api.stripe.com", auth=(publishable_key, ""), timeout=30)


def print_report(report: SeedReport) -> None:
    for card in report.cards:
        if card.error:
            print(f"FAILED   card for {card.name}: {card.error}")
        else:
            print(
                f"card     {card.name}: {'test Visa saved' if card.saved else 'already has a card'}"
            )
    for driver in report.drivers:
        if driver.error:
            print(f"FAILED   {driver.name}: {driver.error}")
        else:
            series = " (1 recurring series)" if driver.series else ""
            print(
                f"posted   {driver.name}: {driver.posted} new trips{series}, "
                f"{driver.already_there} already there"
            )
    for request in report.requests:
        if request.error:
            print(f"FAILED   request {request.name}: {request.error}")
        else:
            how = "new, " if request.created else ""
            print(f"request  {request.name}: {how}{request.status}")
    if report.skipped_payments:
        print(
            "skipped  cards and seat requests: set STRIPE_PUBLISHABLE_KEY (pk_test_...) "
            "to the same Stripe sandbox as Payments"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill the demo through the API (#111, #180).")
    parser.add_argument("--site", default="http://localhost", help="the gateway's address")
    parser.add_argument("--days", type=int, default=DAYS_AHEAD, help="how many days ahead")
    args = parser.parse_args(argv)

    password = os.environ.get("SEED_PASSWORD", "")
    if not password:
        print("Set SEED_PASSWORD to the demo accounts' password.", file=sys.stderr)
        return 2
    try:
        data = load_demo_data()
        key = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
        stripe = stripe_client(key) if key else None
    except (DemoDataError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    with httpx.Client(base_url=args.site, timeout=30) as client:
        try:
            report = seed_trips(client, data, password, datetime.now(UTC), args.days, stripe=stripe)
        finally:
            if stripe is not None:
                stripe.close()

    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
