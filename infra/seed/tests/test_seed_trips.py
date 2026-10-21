"""The demo trips script (#111): the dates it picks, and what it sends, against a fake API."""

import json
from datetime import UTC, datetime, time
from typing import Any

import httpx
import pytest
import seed_trips as script
from demo_data import DemoData, Person, Place, TripPlan
from seed_trips import DriverReport, SeedReport, departures, main, seed_trips

PASSWORD = "demo password 2026"  # noqa: S105 (a test password)
# Monday 27 October 2025, 06:00 in Winnipeg (11:00 UTC). 2025 because Winnipeg's clocks
# went back on 2 November that year; tzdata 2026.5 keeps Manitoba on UTC-5 from 2026 on.
MONDAY_MORNING = datetime(2025, 10, 27, 11, 0, tzinfo=UTC)
HOME = Place("Osborne Village", 49.8806, -97.143)


def plan(weekdays: tuple[Any, ...], at: time, direction: Any = "to_campus") -> TripPlan:
    return TripPlan(direction, weekdays, at, seats=3)


def driver(name: str, *trips: TripPlan) -> Person:
    return Person(f"getdrove.demo.{name.lower()}@myumanitoba.ca", name, "Test", HOME, trips)


# ---------------------------------------------------------------- the dates


def test_trips_go_on_the_listed_weekdays_for_two_weeks() -> None:
    leaving = departures(plan(("mon", "wed", "fri"), time(7, 45)), MONDAY_MORNING)

    assert [d.strftime("%a %d") for d in leaving] == [
        "Mon 27", "Wed 29", "Fri 31", "Mon 03", "Wed 05", "Fri 07",
    ]  # fmt: skip


def test_winnipeg_times_become_utc_with_daylight_saving() -> None:
    leaving = departures(plan(("mon",), time(7, 45)), MONDAY_MORNING)

    # 07:45 Winnipeg is 12:45 UTC before daylight saving ends (2 November), 13:45 after.
    assert leaving == [
        datetime(2025, 10, 27, 12, 45, tzinfo=UTC),
        datetime(2025, 11, 3, 13, 45, tzinfo=UTC),
    ]


def test_a_time_already_past_today_is_left_out() -> None:
    late_monday = datetime(2025, 10, 27, 22, 0, tzinfo=UTC)  # 17:00 in Winnipeg

    leaving = departures(plan(("mon",), time(16, 30)), late_monday)

    assert leaving == [datetime(2025, 11, 3, 22, 30, tzinfo=UTC)]  # next Monday only


def test_the_number_of_days_can_be_changed() -> None:
    assert len(departures(plan(("mon",), time(7, 45)), MONDAY_MORNING, days=3)) == 1


# ---------------------------------------------------------------- against a fake API


class FakeApi:
    """Answers like the gateway: login, /trips/mine and posting a trip."""

    def __init__(
        self, *, existing_trips: set[str] = frozenset(), bad_logins: set[str] = frozenset()
    ):  # type: ignore[assignment]
        self.existing_trips = existing_trips
        self.bad_logins = bad_logins
        self.posted: list[tuple[str, dict[str, Any]]] = []
        self.refuse_posts = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/accounts/auth/login":
            email = json.loads(request.content)["email"]
            if email in self.bad_logins:
                return httpx.Response(401, json={"code": "invalid_credentials"})
            return httpx.Response(200, json={"accessToken": f"token-{email}", "expiresIn": 900})
        token = request.headers["Authorization"].removeprefix("Bearer token-")
        if request.url.path == "/api/trips/mine":
            assert request.url.params["role"] == "driver"
            return httpx.Response(200, json=[{"id": "t1"}] if token in self.existing_trips else [])
        if request.url.path == "/api/trips/" and request.method == "POST":
            if self.refuse_posts:
                return httpx.Response(503, json={"code": "routing_unavailable"})
            self.posted.append((token, json.loads(request.content)))
            return httpx.Response(201, json={"id": "new"})
        return httpx.Response(404)


def run(api: FakeApi, *drivers: Person) -> Any:
    client = httpx.Client(transport=httpx.MockTransport(api.handle), base_url="http://test")
    return seed_trips(client, DemoData(drivers=drivers, riders=()), PASSWORD, MONDAY_MORNING)


def test_it_posts_each_drivers_trips_as_that_driver() -> None:
    api = FakeApi()
    maya = driver(
        "Maya",
        plan(("mon", "wed", "fri"), time(7, 45)),
        plan(("mon",), time(16, 30), "from_campus"),
    )

    report = run(api, maya)

    assert report.ok
    [result] = report.drivers
    assert (result.name, result.posted, result.skipped) == ("Maya Test", 8, False)
    assert {token for token, _ in api.posted} == {maya.email}
    _, first = api.posted[0]
    assert first == {
        "direction": "to_campus",
        "place": {"label": "Osborne Village", "lat": 49.8806, "lng": -97.143},
        "departureAt": "2025-10-27T12:45:00Z",
        "seatsTotal": 3,
    }


def test_drivers_who_already_have_trips_are_skipped() -> None:
    maya, tomas = (
        driver("Maya", plan(("mon",), time(8, 0))),
        driver("Tomas", plan(("tue",), time(8, 0))),
    )
    api = FakeApi(existing_trips={maya.email})

    report = run(api, maya, tomas)

    assert [(d.name, d.skipped, d.posted) for d in report.drivers] == [
        ("Maya Test", True, 0),
        ("Tomas Test", False, 2),
    ]


def test_one_driver_failing_doesnt_stop_the_others() -> None:
    maya, tomas = (
        driver("Maya", plan(("mon",), time(8, 0))),
        driver("Tomas", plan(("tue",), time(8, 0))),
    )
    api = FakeApi(bad_logins={maya.email})

    report = run(api, maya, tomas)

    assert not report.ok
    assert "couldn't log in (401 invalid_credentials)" in (report.drivers[0].error or "")
    assert report.drivers[1].posted == 2


def test_a_refused_trip_is_reported_with_the_apis_code() -> None:
    api = FakeApi()
    api.refuse_posts = True

    report = run(api, driver("Maya", plan(("mon",), time(8, 0))))

    assert report.drivers[0].error == "a trip was refused (503 routing_unavailable)"


def test_an_unreachable_site_is_reported() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(transport=httpx.MockTransport(down), base_url="http://test")
    report = seed_trips(
        client,
        DemoData(drivers=(driver("Maya", plan(("mon",), time(8, 0))),), riders=()),
        PASSWORD,
        MONDAY_MORNING,
    )

    assert (report.drivers[0].error or "").startswith("couldn't reach the site")


def test_without_a_password_it_does_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SEED_PASSWORD", raising=False)

    assert main(["--site", "http://test"]) == 2
    assert "SEED_PASSWORD" in capsys.readouterr().err


def test_a_failed_trip_list_is_reported() -> None:
    def no_trips_service(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json={"accessToken": "t", "expiresIn": 900})
        return httpx.Response(502, text="Bad Gateway")  # not Problem Details JSON

    client = httpx.Client(transport=httpx.MockTransport(no_trips_service), base_url="http://test")
    report = seed_trips(
        client,
        DemoData(drivers=(driver("Maya", plan(("mon",), time(8, 0))),), riders=()),
        PASSWORD,
        MONDAY_MORNING,
    )

    assert report.drivers[0].error == "couldn't list their trips (502)"


def test_main_prints_a_line_per_driver_and_fails_if_any_did(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    report = SeedReport(
        [
            DriverReport("Maya Chen", posted=12),
            DriverReport("Tomas Rivera", skipped=True),
            DriverReport("Aisha Okafor", error="couldn't log in (401)"),
        ]
    )
    monkeypatch.setattr(script, "seed_trips", lambda *args: report)

    assert main(["--site", "http://test"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "posted   Maya Chen: 12 trips",
        "skipped  Tomas Rivera: already has upcoming trips",
        "FAILED   Aisha Okafor: couldn't log in (401)",
    ]


def test_main_succeeds_when_every_driver_does(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setattr(script, "seed_trips", lambda *args: SeedReport([DriverReport("Maya Chen")]))

    assert main([]) == 0
