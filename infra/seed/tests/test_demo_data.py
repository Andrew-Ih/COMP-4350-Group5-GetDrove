"""infra/seed/demo.json (#111, #180): the real file is valid, and mistakes are reported
clearly."""

import copy
from datetime import time
from typing import Any

import pytest
from demo_data import DemoDataError, SeatRequestPlan, Vehicle, load_demo_data, parse_demo_data

DRIVER = {
    "email": "getdrove.demo.maya@myumanitoba.ca",
    "firstName": "Maya",
    "lastName": "Chen",
    "home": {"label": "Osborne Village", "lat": 49.8806, "lng": -97.143},
    "trips": [{"direction": "to_campus", "weekdays": ["mon"], "departAt": "07:45", "seats": 3}],
    "vehicle": {"make": "Toyota", "model": "Corolla", "colour": "Blue", "plate": "gdmaya1"},
}
RIDER = {
    "email": "getdrove.demo.priya@myumanitoba.ca",
    "firstName": "Priya",
    "lastName": "Sharma",
    "home": {"label": "Corydon Ave", "lat": 49.8722, "lng": -97.1561},
    "card": True,
}
ADMIN = {"email": "getdrove.demo.admin@myumanitoba.ca", "firstName": "Alex", "lastName": "Morgan"}
REQUEST = {
    "rider": RIDER["email"],
    "driver": DRIVER["email"],
    "direction": "to_campus",
    "status": "accepted",
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
    assert all(driver.vehicle for driver in demo.drivers)
    assert all(driver.trips for driver in demo.drivers if driver.approved)
    # What #180 adds: someone for the admin to approve, a series, cards and requests.
    assert any(not driver.approved for driver in demo.drivers)
    assert any(plan.repeat for driver in demo.drivers for plan in driver.trips)
    assert any(rider.card for rider in demo.riders)
    assert any(not rider.card for rider in demo.riders)  # sees the "add a card" prompt
    assert {plan.status for plan in demo.requests} == {"pending", "accepted"}
    assert demo.admin is not None


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
    assert not trip.repeat
    assert maya.vehicle == Vehicle("Toyota", "Corolla", "Blue", "GDMAYA1")  # plate uppercased
    assert maya.approved
    assert demo.people == demo.drivers + demo.riders
    assert demo.riders[0].card
    assert demo.admin is None
    assert demo.requests == ()


def test_it_reads_the_admin_and_the_seat_requests() -> None:
    demo = parse_demo_data(data(admin=ADMIN, requests=[REQUEST]))

    assert demo.admin is not None
    assert (demo.admin.email, demo.admin.first_name) == (ADMIN["email"], "Alex")
    assert demo.requests == (
        SeatRequestPlan(RIDER["email"], DRIVER["email"], "to_campus", "accepted"),
    )
    assert demo.person(RIDER["email"]).first_name == "Priya"


def test_a_pending_driver_has_a_car_but_no_trips() -> None:
    raw = data()
    raw["drivers"][0]["approval"] = "pending"
    raw["drivers"][0]["trips"] = []

    [sam] = parse_demo_data(raw).drivers
    assert not sam.approved
    assert sam.trips == ()


def test_a_pending_driver_cant_post_trips() -> None:
    raw = data()
    raw["drivers"][0]["approval"] = "pending"

    assert problems_for(raw) == ["drivers[0].trips: a pending driver can't post trips"]


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
        ({"repeat": "yes"}, "repeat"),
    ],
)
def test_trip_mistakes_name_the_field(change: dict[str, Any], field: str) -> None:
    raw = data()
    raw["drivers"][0]["trips"][0].update(change)

    [problem] = problems_for(raw)
    assert problem.startswith(f"drivers[0].trips[0].{field}")


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"approval": "maybe"}, "drivers[0].approval"),
        ({"vehicle": None}, "drivers[0].vehicle"),
        ({"vehicle": {"make": "Toyota"}}, "drivers[0].vehicle"),
        ({"vehicle": {**DRIVER["vehicle"], "plate": "GD-MAYA"}}, "drivers[0].vehicle.plate"),
        ({"vehicle": {**DRIVER["vehicle"], "colour": "x" * 31}}, "drivers[0].vehicle"),
    ],
)
def test_driver_mistakes_name_the_field(change: dict[str, Any], problem: str) -> None:
    raw = data()
    raw["drivers"][0].update(change)

    [found] = problems_for(raw)
    assert found.startswith(problem)


def test_card_must_be_true_or_false() -> None:
    raw = data()
    raw["riders"][0]["card"] = "yes"

    assert problems_for(raw) == ["riders[0].card: must be true or false"]


def test_the_admin_cant_share_an_email_or_miss_a_name() -> None:
    assert problems_for(data(admin={**ADMIN, "email": DRIVER["email"]})) == [
        f"{DRIVER['email']} appears more than once"
    ]
    [problem] = problems_for(data(admin={**ADMIN, "lastName": ""}))
    assert problem.startswith("admin.lastName")
    [problem] = problems_for(data(admin="Alex"))
    assert problem.startswith("admin:")


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"rider": "getdrove.demo.nobody@myumanitoba.ca"}, "requests[0].rider: must be one"),
        ({"rider": DRIVER["email"]}, "requests[0].rider: must be one"),
        ({"driver": RIDER["email"]}, "requests[0].driver"),
        ({"direction": "from_campus"}, "requests[0].direction: the driver has no trip"),
        ({"direction": "home"}, "requests[0].direction: must be"),
        ({"status": "declined"}, "requests[0].status"),
    ],
)
def test_request_mistakes_name_the_field(change: dict[str, Any], problem: str) -> None:
    [found] = problems_for(data(requests=[{**REQUEST, **change}]))
    assert found.startswith(problem)


def test_a_rider_needs_a_card_to_request_a_seat() -> None:
    raw = data(requests=[REQUEST])
    raw["riders"][0]["card"] = False

    assert problems_for(raw) == ['requests[0].rider: needs "card": true to request a seat']


def test_a_pending_driver_cant_be_asked_for_a_seat() -> None:
    raw = data(requests=[REQUEST])
    raw["drivers"][0]["approval"] = "pending"
    raw["drivers"][0]["trips"] = []

    [problem] = problems_for(raw)
    assert problem.startswith("requests[0].driver")


def test_the_same_request_twice_is_refused() -> None:
    [problem] = problems_for(data(requests=[REQUEST, {**REQUEST, "status": "pending"}]))
    assert problem.endswith("to_campus twice")


def test_requests_must_be_a_list() -> None:
    assert problems_for(data(requests={})) == ["requests: must be a list"]


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
