"""Reads and checks infra/seed/demo.json: the demo accounts, their commutes, cars and cards,
and the seat requests to set up (#111, #180).

The file is meant to be edited by hand, so every mistake is reported at once, with where
it is, before anything is created:

    data = load_demo_data()            # raises DemoDataError listing every problem
    for driver in data.drivers: ...

Standard library only, so it runs anywhere ``uv run`` does.
"""

import json
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any, Literal, cast

DEMO_FILE = Path(__file__).with_name("demo.json")

# Demo emails can't belong to a real student, who then couldn't sign up ("email taken").
EMAIL_PREFIX = "getdrove.demo."
EMAIL_DOMAIN = "@myumanitoba.ca"
# The area the OSRM image covers (BBOX in infra/osrm/Dockerfile); routes can't leave it.
WEST, SOUTH, EAST, NORTH = -97.45, 49.70, -96.85, 50.05
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")
DIRECTIONS = ("to_campus", "from_campus")
MIN_SEATS, MAX_SEATS = 1, 6  # the Trips contract's seatsTotal range
APPROVALS = ("approved", "pending")
REQUEST_STATUSES = ("pending", "accepted")

Weekday = Literal["mon", "tue", "wed", "thu", "fri"]
Direction = Literal["to_campus", "from_campus"]


class DemoDataError(ValueError):
    """demo.json has mistakes; ``problems`` lists each one with where it is."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("demo.json has problems:\n" + "\n".join(f"- {p}" for p in problems))
        self.problems = problems


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lng: float


@dataclass(frozen=True)
class TripPlan:
    """A weekly commute: one trip on each of ``weekdays``, leaving at ``depart_at``
    Winnipeg time."""

    direction: Direction
    weekdays: tuple[Weekday, ...]
    depart_at: time
    seats: int
    repeat: bool = False  # posted as one recurring series (#15) rather than single trips


@dataclass(frozen=True)
class Vehicle:
    make: str
    model: str
    colour: str
    plate: str


@dataclass(frozen=True)
class Person:
    email: str
    first_name: str
    last_name: str
    home: Place
    trips: tuple[TripPlan, ...] = ()
    vehicle: Vehicle | None = None  # drivers only
    approved: bool = True  # drivers: False is left pending for the admin, posts nothing
    card: bool = False  # riders: given Stripe's test Visa, so they can request seats


@dataclass(frozen=True)
class Admin:
    email: str
    first_name: str
    last_name: str


@dataclass(frozen=True)
class SeatRequestPlan:
    """A rider asking for a seat on the driver's next trip that way; ``accepted`` ones are
    then accepted by the driver."""

    rider: str  # email
    driver: str  # email
    direction: Direction
    status: Literal["pending", "accepted"]


@dataclass(frozen=True)
class DemoData:
    drivers: tuple[Person, ...]
    riders: tuple[Person, ...]
    admin: Admin | None = None
    requests: tuple[SeatRequestPlan, ...] = ()

    @property
    def people(self) -> tuple[Person, ...]:
        return self.drivers + self.riders

    def person(self, email: str) -> Person:
        return next(p for p in self.people if p.email == email)


def load_demo_data(path: Path = DEMO_FILE) -> DemoData:
    return parse_demo_data(json.loads(path.read_text(encoding="utf-8")))


def parse_demo_data(raw: Any) -> DemoData:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise DemoDataError(["the file must be a JSON object with drivers and riders"])

    drivers = _people(raw.get("drivers"), "drivers", problems, needs_trips=True)
    riders = _people(raw.get("riders"), "riders", problems, needs_trips=False)
    admin = _admin(raw.get("admin"), problems) if "admin" in raw else None

    seen: set[str] = set()
    for email in [p.email for p in drivers + riders] + ([admin.email] if admin else []):
        if email in seen:
            problems.append(f"{email} appears more than once")
        seen.add(email)

    requests = _requests(raw.get("requests", []), drivers, riders, problems)

    if problems:
        raise DemoDataError(problems)
    return DemoData(tuple(drivers), tuple(riders), admin, tuple(requests))


def _people(raw: Any, key: str, problems: list[str], *, needs_trips: bool) -> list[Person]:
    if not isinstance(raw, list) or not raw:
        problems.append(f"{key}: must be a non-empty list")
        return []
    people = []
    for index, item in enumerate(raw):
        where = f"{key}[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: must be an object")
            continue
        email = _email(item.get("email"), where, problems)
        first = _name(item.get("firstName"), f"{where}.firstName", problems)
        last = _name(item.get("lastName"), f"{where}.lastName", problems)
        home = _place(item.get("home"), f"{where}.home", problems)
        trips: list[TripPlan] = []
        vehicle: Vehicle | None = None
        approved = True
        card = False
        if needs_trips:
            approval = item.get("approval", "approved")
            if approval not in APPROVALS:
                problems.append(f"{where}.approval: must be approved or pending")
            approved = approval != "pending"
            vehicle = _vehicle(item.get("vehicle"), f"{where}.vehicle", problems)
            raw_trips = item.get("trips", [])
            if not isinstance(raw_trips, list) or (approved and not raw_trips):
                problems.append(f"{where}.trips: a driver needs at least one trip")
            elif not approved and raw_trips:
                problems.append(f"{where}.trips: a pending driver can't post trips")
            else:
                for t, raw_trip in enumerate(raw_trips):
                    plan = _trip(raw_trip, f"{where}.trips[{t}]", problems)
                    if plan:
                        trips.append(plan)
        else:
            if "trips" in item:
                problems.append(f"{where}.trips: riders don't post trips")
            card = item.get("card", False)
            if not isinstance(card, bool):
                problems.append(f"{where}.card: must be true or false")
        if email and first and last and home:
            people.append(
                Person(email, first, last, home, tuple(trips), vehicle, approved, card is True)
            )
    return people


def _admin(raw: Any, problems: list[str]) -> Admin | None:
    if not isinstance(raw, dict):
        problems.append("admin: must be an object with email, firstName and lastName")
        return None
    email = _email(raw.get("email"), "admin", problems)
    first = _name(raw.get("firstName"), "admin.firstName", problems)
    last = _name(raw.get("lastName"), "admin.lastName", problems)
    return Admin(email, first, last) if email and first and last else None


def _vehicle(raw: Any, where: str, problems: list[str]) -> Vehicle | None:
    """The Accounts rules (#125): 1 to 30 characters each, a plate of 2 to 8 letters and
    numbers."""
    if not isinstance(raw, dict):
        problems.append(f"{where}: a driver needs make, model, colour and plate")
        return None
    fields = [raw.get(key) for key in ("make", "model", "colour", "plate")]
    if not all(isinstance(value, str) and 1 <= len(value.strip()) <= 30 for value in fields):
        problems.append(f"{where}: make, model, colour and plate must be 1 to 30 characters")
        return None
    make, model, colour, plate = (str(value).strip() for value in fields)
    if not re.fullmatch(r"[A-Z0-9]{2,8}", plate.upper()):
        problems.append(f"{where}.plate: use 2 to 8 letters and numbers")
        return None
    return Vehicle(make, model, colour, plate.upper())


def _requests(
    raw: Any, drivers: list[Person], riders: list[Person], problems: list[str]
) -> list[SeatRequestPlan]:
    if not isinstance(raw, list):
        problems.append("requests: must be a list")
        return []
    by_email = {p.email: p for p in drivers + riders}
    plans = []
    for index, item in enumerate(raw):
        where = f"requests[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: must be an object")
            continue
        rider = by_email.get(str(item.get("rider", "")).lower())
        driver = by_email.get(str(item.get("driver", "")).lower())
        direction, status = item.get("direction"), item.get("status")
        if rider is None or rider not in riders:
            problems.append(f"{where}.rider: must be one of the riders' emails")
        elif not rider.card:
            problems.append(f'{where}.rider: needs "card": true to request a seat')
        if driver is None or driver not in drivers or not driver.approved:
            problems.append(f"{where}.driver: must be one of the approved drivers' emails")
        elif direction in DIRECTIONS and not any(p.direction == direction for p in driver.trips):
            problems.append(f"{where}.direction: the driver has no trip that way")
        if direction not in DIRECTIONS:
            problems.append(f"{where}.direction: must be to_campus or from_campus")
        if status not in REQUEST_STATUSES:
            problems.append(f"{where}.status: must be pending or accepted")
        if rider and driver and direction in DIRECTIONS and status in REQUEST_STATUSES:
            plans.append(
                SeatRequestPlan(
                    rider.email,
                    driver.email,
                    cast(Direction, direction),
                    cast(Literal["pending", "accepted"], status),
                )
            )
    seen = set()
    for plan in plans:
        key = (plan.rider, plan.driver, plan.direction)
        if key in seen:
            problems.append(f"{plan.rider} asks {plan.driver} for a seat {plan.direction} twice")
        seen.add(key)
    return plans


def _email(raw: Any, where: str, problems: list[str]) -> str | None:
    if not isinstance(raw, str):
        problems.append(f"{where}.email: missing")
        return None
    email = raw.strip().lower()
    local = email.removesuffix(EMAIL_DOMAIN)
    if not email.endswith(EMAIL_DOMAIN) or not local.startswith(EMAIL_PREFIX):
        problems.append(f"{where}.email: must look like {EMAIL_PREFIX}<name>{EMAIL_DOMAIN}")
        return None
    if not re.fullmatch(r"[a-z0-9_%+-]+(\.[a-z0-9_%+-]+)*", local):
        problems.append(f"{where}.email: {raw!r} isn't a valid address")
        return None
    return email


def _name(raw: Any, where: str, problems: list[str]) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > 50:
        problems.append(f"{where}: must be 1 to 50 characters")
        return None
    return raw.strip()


def _place(raw: Any, where: str, problems: list[str]) -> Place | None:
    if not isinstance(raw, dict):
        problems.append(f"{where}: must have a label, lat and lng")
        return None
    label, lat, lng = raw.get("label"), raw.get("lat"), raw.get("lng")
    if not isinstance(label, str) or not label.strip():
        problems.append(f"{where}.label: missing")
        return None
    if not isinstance(lat, int | float) or not isinstance(lng, int | float):
        problems.append(f"{where}: lat and lng must be numbers")
        return None
    if not (SOUTH <= lat <= NORTH and WEST <= lng <= EAST):
        problems.append(f"{where}: ({lat}, {lng}) is outside the Winnipeg map area")
        return None
    return Place(label.strip(), float(lat), float(lng))


def _trip(raw: Any, where: str, problems: list[str]) -> TripPlan | None:
    if not isinstance(raw, dict):
        problems.append(f"{where}: must be an object")
        return None
    direction = raw.get("direction")
    weekdays = raw.get("weekdays")
    depart_at = raw.get("departAt")
    seats = raw.get("seats")
    repeat = raw.get("repeat", False)
    ok = True
    if not isinstance(repeat, bool):
        problems.append(f"{where}.repeat: must be true or false")
        ok = False
    if direction not in DIRECTIONS:
        problems.append(f"{where}.direction: must be to_campus or from_campus")
        ok = False
    if (
        not isinstance(weekdays, list)
        or not weekdays
        or any(day not in WEEKDAYS for day in weekdays)
        or len(set(weekdays)) != len(weekdays)
    ):
        problems.append(f"{where}.weekdays: a list of different days from mon to fri")
        ok = False
    parsed_time = _time(depart_at)
    if parsed_time is None:
        problems.append(f"{where}.departAt: must be HH:MM, 24-hour (e.g. 07:45)")
        ok = False
    if not isinstance(seats, int) or isinstance(seats, bool) or not MIN_SEATS <= seats <= MAX_SEATS:
        problems.append(f"{where}.seats: must be a whole number from {MIN_SEATS} to {MAX_SEATS}")
        ok = False
    if not ok or parsed_time is None:
        return None
    # Checked above against DIRECTIONS and WEEKDAYS.
    return TripPlan(
        cast(Direction, direction),
        cast(tuple[Weekday, ...], tuple(cast(list[str], weekdays))),
        parsed_time,
        cast(int, seats),
        repeat is True,
    )


def _time(raw: Any) -> time | None:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{2}:\d{2}", raw):
        return None
    hours, minutes = int(raw[:2]), int(raw[3:])
    if hours > 23 or minutes > 59:
        return None
    return time(hours, minutes)
