"""Reads and checks infra/seed/demo.json: the demo accounts and their commutes (#111).

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


@dataclass(frozen=True)
class Person:
    email: str
    first_name: str
    last_name: str
    home: Place
    trips: tuple[TripPlan, ...] = ()


@dataclass(frozen=True)
class DemoData:
    drivers: tuple[Person, ...]
    riders: tuple[Person, ...]

    @property
    def people(self) -> tuple[Person, ...]:
        return self.drivers + self.riders


def load_demo_data(path: Path = DEMO_FILE) -> DemoData:
    return parse_demo_data(json.loads(path.read_text(encoding="utf-8")))


def parse_demo_data(raw: Any) -> DemoData:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise DemoDataError(["the file must be a JSON object with drivers and riders"])

    drivers = _people(raw.get("drivers"), "drivers", problems, needs_trips=True)
    riders = _people(raw.get("riders"), "riders", problems, needs_trips=False)

    seen: set[str] = set()
    for person in drivers + riders:
        if person.email in seen:
            problems.append(f"{person.email} appears more than once")
        seen.add(person.email)

    if problems:
        raise DemoDataError(problems)
    return DemoData(drivers=tuple(drivers), riders=tuple(riders))


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
        if needs_trips:
            raw_trips = item.get("trips")
            if not isinstance(raw_trips, list) or not raw_trips:
                problems.append(f"{where}.trips: a driver needs at least one trip")
            else:
                for t, raw_trip in enumerate(raw_trips):
                    plan = _trip(raw_trip, f"{where}.trips[{t}]", problems)
                    if plan:
                        trips.append(plan)
        elif "trips" in item:
            problems.append(f"{where}.trips: riders don't post trips")
        if email and first and last and home:
            people.append(Person(email, first, last, home, tuple(trips)))
    return people


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
    ok = True
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
    )


def _time(raw: Any) -> time | None:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{2}:\d{2}", raw):
        return None
    hours, minutes = int(raw[:2]), int(raw[3:])
    if hours > 23 or minutes > 59:
        return None
    return time(hours, minutes)
