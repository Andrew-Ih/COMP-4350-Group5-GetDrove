"""infra/seed/demo.json (#111): the real file is valid, and mistakes are reported clearly."""

import copy
from datetime import time
from typing import Any

import pytest
from demo_data import DemoDataError, load_demo_data, parse_demo_data

DRIVER = {
    "email": "getdrove.demo.maya@myumanitoba.ca",
    "firstName": "Maya",
    "lastName": "Chen",
    "home": {"label": "Osborne Village", "lat": 49.8806, "lng": -97.143},
    "trips": [{"direction": "to_campus", "weekdays": ["mon"], "departAt": "07:45", "seats": 3}],
}
RIDER = {
    "email": "getdrove.demo.priya@myumanitoba.ca",
    "firstName": "Priya",
    "lastName": "Sharma",
    "home": {"label": "Corydon Ave", "lat": 49.8722, "lng": -97.1561},
}


def data(**changes: Any) -> dict[str, Any]:
    raw = {"drivers": [copy.deepcopy(DRIVER)], "riders": [copy.deepcopy(RIDER)]}
    raw.update(changes)
    return raw


def problems_for(raw: dict[str, Any]) -> list[str]:
    with pytest.raises(DemoDataError) as caught:
        parse_demo_data(raw)
    return caught.value.problems


# ---------------------------------------------------------------- the real file


def test_the_committed_demo_file_is_valid() -> None:
    demo = load_demo_data()

    assert len(demo.drivers) >= 2
    assert len(demo.riders) >= 2
    assert all(driver.trips for driver in demo.drivers)


def test_it_reads_a_driver_and_their_commute() -> None:
    demo = parse_demo_data(data())

    [maya] = demo.drivers
    assert maya.email == "getdrove.demo.maya@myumanitoba.ca"
    assert (maya.home.label, maya.home.lat, maya.home.lng) == ("Osborne Village", 49.8806, -97.143)
    [trip] = maya.trips
    assert (trip.direction, trip.weekdays, trip.depart_at, trip.seats) == (
        "to_campus",
        ("mon",),
        time(7, 45),
        3,
    )
    assert demo.people == demo.drivers + demo.riders


# ---------------------------------------------------------------- mistakes


@pytest.mark.parametrize(
    "email",
    [
        "maya@myumanitoba.ca",  # no demo prefix: could be a real student
        "getdrove.demo.maya@gmail.com",
        "getdrove.demo.maya b@myumanitoba.ca",
    ],
)
def test_emails_must_be_demo_uofm_addresses(email: str) -> None:
    raw = data()
    raw["drivers"][0]["email"] = email

    [problem] = problems_for(raw)
    assert problem.startswith("drivers[0].email")


def test_the_same_email_twice_is_refused() -> None:
    raw = data()
    raw["riders"][0]["email"] = DRIVER["email"]

    assert problems_for(raw) == [f"{DRIVER['email']} appears more than once"]


@pytest.mark.parametrize(("lat", "lng"), [(45.42, -75.69), (49.9, -96.5), ("49.9", -97.1)])
def test_homes_must_be_inside_the_winnipeg_map(lat: Any, lng: Any) -> None:
    raw = data()
    raw["riders"][0]["home"] = {"label": "Elsewhere", "lat": lat, "lng": lng}

    [problem] = problems_for(raw)
    assert problem.startswith("riders[0].home")


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"direction": "to_airport"}, "direction"),
        ({"weekdays": ["sat"]}, "weekdays"),
        ({"weekdays": ["mon", "mon"]}, "weekdays"),
        ({"weekdays": []}, "weekdays"),
        ({"departAt": "7:45"}, "departAt"),
        ({"departAt": "25:00"}, "departAt"),
        ({"seats": 0}, "seats"),
        ({"seats": 7}, "seats"),
        ({"seats": True}, "seats"),
    ],
)
def test_trip_mistakes_name_the_field(change: dict[str, Any], field: str) -> None:
    raw = data()
    raw["drivers"][0]["trips"][0].update(change)

    [problem] = problems_for(raw)
    assert problem.startswith(f"drivers[0].trips[0].{field}")


def test_drivers_need_trips_and_riders_cant_have_them() -> None:
    raw = data()
    raw["drivers"][0]["trips"] = []
    raw["riders"][0]["trips"] = DRIVER["trips"]

    assert problems_for(raw) == [
        "drivers[0].trips: a driver needs at least one trip",
        "riders[0].trips: riders don't post trips",
    ]


def test_every_problem_is_reported_at_once() -> None:
    raw = data()
    raw["drivers"][0]["firstName"] = ""
    raw["drivers"][0]["trips"][0]["seats"] = 9
    raw["riders"][0]["home"]["lat"] = 10

    assert len(problems_for(raw)) == 3


@pytest.mark.parametrize("raw", [[], {"drivers": [], "riders": []}, {"drivers": "x"}])
def test_the_file_shape_is_checked(raw: Any) -> None:
    with pytest.raises(DemoDataError):
        parse_demo_data(raw)


@pytest.mark.parametrize(
    ("break_it", "where"),
    [
        (lambda raw: raw["riders"].__setitem__(0, "Priya"), "riders[0]"),
        (lambda raw: raw["riders"][0].pop("email"), "riders[0].email"),
        (lambda raw: raw["riders"][0].__setitem__("home", "Corydon"), "riders[0].home"),
        (lambda raw: raw["riders"][0]["home"].__setitem__("label", " "), "riders[0].home.label"),
        (lambda raw: raw["drivers"][0]["trips"].__setitem__(0, "mon"), "drivers[0].trips[0]"),
    ],
)
def test_malformed_entries_name_where_they_are(break_it: Any, where: str) -> None:
    raw = data()
    break_it(raw)

    [problem] = problems_for(raw)
    assert problem.startswith(where)
