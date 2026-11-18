"""The demo script (#111, #180): the dates it picks, and what it sends, against a fake API
and a fake Stripe."""

import json
from datetime import UTC, datetime, time
from typing import Any

import httpx
import pytest
import seed_trips as script
from demo_data import DemoData, Person, Place, SeatRequestPlan, TripPlan
from seed_trips import (
    CardReport,
    DriverReport,
    RequestReport,
    SeedReport,
    departures,
    main,
    seed_trips,
    stripe_client,
)

PASSWORD = "demo password 2026"  # noqa: S105 (a test password)
# Monday 27 October 2025, 06:00 in Winnipeg (11:00 UTC). 2025 because Winnipeg's clocks
# went back on 2 November that year; tzdata 2026.5 keeps Manitoba on UTC-5 from 2026 on.
MONDAY_MORNING = datetime(2025, 10, 27, 11, 0, tzinfo=UTC)
HOME = Place("Osborne Village", 49.8806, -97.143)


RIDER_HOME = Place("Corydon Ave", 49.8722, -97.1561)


def plan(
    weekdays: tuple[Any, ...], at: time, direction: Any = "to_campus", *, repeat: bool = False
) -> TripPlan:
    return TripPlan(direction, weekdays, at, seats=3, repeat=repeat)


def driver(name: str, *trips: TripPlan, approved: bool = True) -> Person:
    email = f"getdrove.demo.{name.lower()}@myumanitoba.ca"
    return Person(email, name, "Test", HOME, trips, approved=approved)


def rider(name: str, *, card: bool = True) -> Person:
    return Person(
        f"getdrove.demo.{name.lower()}@myumanitoba.ca", name, "Test", RIDER_HOME, card=card
    )


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


def test_winnipeg_stays_on_utc_minus_5_from_november_2026() -> None:
    """tzdata 2026e: Manitoba no longer goes back to UTC-6 in November. An older system
    time zone file would give 13:45 for the second Monday; the script must not use it."""
    friday = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)

    leaving = departures(plan(("mon",), time(7, 45)), friday, days=7)

    assert leaving == [datetime(2026, 11, 2, 12, 45, tzinfo=UTC)]


def test_the_number_of_days_can_be_changed() -> None:
    assert len(departures(plan(("mon",), time(7, 45)), MONDAY_MORNING, days=3)) == 1


# ---------------------------------------------------------------- against a fake API


class FakeApi:
    """Answers like the gateway: login, the driver's trips, posting trips and series, cards,
    and seat requests. The token is the person's email, so each call shows who made it."""

    def __init__(
        self,
        existing_trips: dict[str, list[dict[str, Any]]] | None = None,
        bad_logins: frozenset[str] = frozenset(),
    ) -> None:
        self.existing_trips = existing_trips or {}
        self.bad_logins = bad_logins
        self.posted: list[tuple[str, dict[str, Any]]] = []
        self.series: list[tuple[str, dict[str, Any]]] = []
        self.refuse_posts = False
        self.not_approved_yet = 0  # how many posts Trips refuses before DriverApproved arrives
        self.cards: dict[str, list[dict[str, Any]]] = {}
        self.setup_intents: list[str] = []
        self.requests: dict[str, list[dict[str, Any]]] = {}  # rider -> [{trip, request}]
        self.asked: list[tuple[str, str, dict[str, Any]]] = []  # (rider, trip id, body)
        self.accepted: list[tuple[str, str]] = []  # (driver, request id)
        self.detail_params: list[dict[str, str]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/accounts/auth/login":
            email = json.loads(request.content)["email"]
            if email in self.bad_logins:
                return httpx.Response(401, json={"code": "invalid_credentials"})
            return httpx.Response(200, json={"accessToken": f"token-{email}", "expiresIn": 900})
        token = request.headers["Authorization"].removeprefix("Bearer token-")
        if path == "/api/trips/mine":
            assert request.url.params["role"] == "driver"
            return httpx.Response(200, json=self.existing_trips.get(token, []))
        if path in ("/api/trips/", "/api/trips/series") and request.method == "POST":
            if self.refuse_posts:
                return httpx.Response(503, json={"code": "routing_unavailable"})
            if self.not_approved_yet:
                self.not_approved_yet -= 1
                return httpx.Response(403, json={"code": "driver_not_approved"})
            body = json.loads(request.content)
            if path == "/api/trips/series":
                self.series.append((token, body))
                return httpx.Response(
                    201, json={"seriesId": "s1", "trips": [{"id": "t"}] * 8, "skippedDates": []}
                )
            self.posted.append((token, body))
            return httpx.Response(201, json={"id": "new"})
        if path == "/api/payments/methods":
            return httpx.Response(200, json=self.cards.get(token, []))
        if path == "/api/payments/setup-intent":
            self.setup_intents.append(token)
            return httpx.Response(201, json={"clientSecret": "seti_123_secret_abc"})
        if path == "/api/trips/requests/mine":
            return httpx.Response(200, json=self.requests.get(token, []))
        if path.endswith("/accept"):
            request_id = path.split("/")[-2]
            self.accepted.append((token, request_id))
            return httpx.Response(200, json={"id": request_id, "status": "accepted"})
        if path.endswith("/requests") and request.method == "POST":
            trip_id = path.split("/")[-2]
            self.asked.append((token, trip_id, json.loads(request.content)))
            return httpx.Response(201, json={"id": f"r-{trip_id}", "status": "pending"})
        if path.startswith("/api/trips/") and request.method == "GET":
            self.detail_params.append(dict(request.url.params))
            return httpx.Response(200, json={"trip": {}, "pickups": [{"id": "p1"}, {"id": "p2"}]})
        return httpx.Response(404)


class FakeStripe:
    """Stripe's SetupIntent confirm, as called with the publishable key."""

    def __init__(self, status: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = body or {"id": "seti_123", "status": "succeeded"}
        self.confirmed: list[tuple[str, dict[str, list[str]]]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        from urllib.parse import parse_qs

        self.confirmed.append((request.url.path, parse_qs(request.content.decode())))
        return httpx.Response(self.status, json=self.body)


def trip(trip_id: str, direction: str, leaves: str, **more: str) -> dict[str, Any]:
    return {
        "id": trip_id,
        "direction": direction,
        "departureAt": leaves,
        "status": "scheduled",
        "seriesId": None,
        **more,
    }


def run(
    api: FakeApi,
    *drivers: Person,
    riders: tuple[Person, ...] = (),
    requests: tuple[SeatRequestPlan, ...] = (),
    stripe: FakeStripe | None = None,
    waits: list[float] | None = None,
) -> SeedReport:
    client = httpx.Client(transport=httpx.MockTransport(api.handle), base_url="http://test")
    stripe_api = (
        httpx.Client(transport=httpx.MockTransport(stripe.handle), base_url="https://stripe")
        if stripe
        else None
    )
    return seed_trips(
        client,
        DemoData(drivers=drivers, riders=riders, requests=requests),
        PASSWORD,
        MONDAY_MORNING,
        stripe=stripe_api,
        wait=(waits if waits is not None else []).append,
    )


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
    assert (result.name, result.posted, result.already_there) == ("Maya Test", 8, 0)
    assert {token for token, _ in api.posted} == {maya.email}
    _, first = api.posted[0]
    assert first == {
        "direction": "to_campus",
        "place": {"label": "Osborne Village", "lat": 49.8806, "lng": -97.143},
        "departureAt": "2025-10-27T12:45:00Z",
        "seatsTotal": 3,
    }


def test_only_the_missing_departures_are_posted() -> None:
    """Running it again tops up the two weeks without posting the same trip twice."""
    maya = driver("Maya", plan(("mon", "wed"), time(8, 0)))
    already = [  # how /trips/mine returns them
        {"id": "a", "direction": "to_campus", "departureAt": "2025-10-27T13:00:00Z"},
        {"id": "b", "direction": "to_campus", "departureAt": "2025-10-29T13:00:00Z"},
        {"id": "c", "direction": "from_campus", "departureAt": "2025-11-03T14:00:00Z"},
    ]
    api = FakeApi(existing_trips={maya.email: already})

    report = run(api, maya)

    [result] = report.drivers
    assert (result.posted, result.already_there) == (2, 2)
    # Mon 3 and Wed 5 November (after the clocks went back). The from_campus trip at the
    # same time on the 3rd doesn't count: it's the other direction.
    assert [body["departureAt"] for _, body in api.posted] == [
        "2025-11-03T14:00:00Z",
        "2025-11-05T14:00:00Z",
    ]


def test_one_driver_failing_doesnt_stop_the_others() -> None:
    maya, tomas = (
        driver("Maya", plan(("mon",), time(8, 0))),
        driver("Tomas", plan(("tue",), time(8, 0))),
    )
    api = FakeApi(bad_logins=frozenset({maya.email}))

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
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
    report = SeedReport(
        [
            DriverReport("Maya Chen", posted=12),
            DriverReport("Tomas Rivera", already_there=18),
            DriverReport("Aisha Okafor", error="couldn't log in (401)"),
        ]
    )
    monkeypatch.setattr(script, "seed_trips", lambda *args, **kwargs: report)

    assert main(["--site", "http://test"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "posted   Maya Chen: 12 new trips, 0 already there",
        "posted   Tomas Rivera: 0 new trips, 18 already there",
        "FAILED   Aisha Okafor: couldn't log in (401)",
    ]


def test_main_succeeds_when_every_driver_does(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
    done = SeedReport([DriverReport("Maya Chen")])
    monkeypatch.setattr(script, "seed_trips", lambda *args, **kwargs: done)

    assert main([]) == 0


# ---------------------------------------------------------------- #180: series, approval


def test_a_pending_driver_posts_nothing() -> None:
    api = FakeApi()

    report = run(api, driver("Sam", approved=False))

    assert report.drivers == []
    assert api.posted == []


def test_a_repeating_commute_is_posted_as_one_four_week_series() -> None:
    api = FakeApi()
    aisha = driver("Aisha", plan(("mon", "wed"), time(8, 0), repeat=True))

    report = run(api, aisha)

    assert api.posted == []
    assert api.series == [
        (
            aisha.email,
            {
                "direction": "to_campus",
                "place": {"label": "Osborne Village", "lat": 49.8806, "lng": -97.143},
                "departureAt": "2025-10-27T13:00:00Z",
                "seatsTotal": 3,
                "weekdays": ["mon", "wed"],
                "endDate": "2025-11-23",
            },
        )
    ]
    [result] = report.drivers
    assert (result.posted, result.series) == (8, 1)


def test_a_series_already_there_isnt_posted_again() -> None:
    aisha = driver("Aisha", plan(("mon",), time(8, 0), repeat=True))
    already = [
        trip("a", "to_campus", "2025-10-27T13:00:00Z", seriesId="s"),
        trip("b", "to_campus", "2025-11-03T14:00:00Z", seriesId="s"),
    ]
    api = FakeApi(existing_trips={aisha.email: already})

    report = run(api, aisha)

    assert api.series == []
    assert (report.drivers[0].posted, report.drivers[0].already_there) == (0, 2)


def test_it_waits_for_trips_to_hear_the_driver_was_approved() -> None:
    api = FakeApi()
    api.not_approved_yet = 2
    waits: list[float] = []

    report = run(api, driver("Maya", plan(("mon",), time(8, 0))), waits=waits)

    assert report.ok
    assert len(api.posted) == 2
    assert waits == [2.0, 2.0]


def test_it_gives_up_if_the_approval_never_arrives() -> None:
    api = FakeApi()
    api.not_approved_yet = 100
    waits: list[float] = []

    report = run(api, driver("Maya", plan(("mon",), time(8, 0))), waits=waits)

    assert report.drivers[0].error == "a trip was refused (403 driver_not_approved)"
    assert len(waits) == script.EVENT_TRIES - 1


# ---------------------------------------------------------------- #180: cards


def test_riders_get_the_test_card_through_a_setup_intent() -> None:
    api, stripe = FakeApi(), FakeStripe()
    priya, owen = rider("Priya"), rider("Owen", card=False)

    report = run(api, riders=(priya, owen), stripe=stripe)

    assert api.setup_intents == [priya.email]  # Owen has no card on purpose
    assert stripe.confirmed == [
        (
            "/v1/setup_intents/seti_123/confirm",
            {"client_secret": ["seti_123_secret_abc"], "payment_method": ["pm_card_visa"]},
        )
    ]
    assert report.cards == [CardReport("Priya Test", saved=True)]


def test_a_rider_who_has_a_card_keeps_it() -> None:
    api, stripe = FakeApi(), FakeStripe()
    priya = rider("Priya")
    api.cards[priya.email] = [{"id": "pm_1", "brand": "visa", "last4": "4242"}]

    report = run(api, riders=(priya,), stripe=stripe)

    assert api.setup_intents == []
    assert stripe.confirmed == []
    assert report.cards == [CardReport("Priya Test")]


@pytest.mark.parametrize(
    ("stripe", "error"),
    [
        (
            FakeStripe(400, {"error": {"code": "resource_missing"}}),
            "Stripe didn't save the test card (400 resource_missing)",
        ),
        (
            FakeStripe(200, {"status": "requires_action"}),
            "Stripe didn't save the test card (200 requires_action)",
        ),
    ],
)
def test_a_card_stripe_refuses_is_reported(stripe: FakeStripe, error: str) -> None:
    report = run(FakeApi(), riders=(rider("Priya"),), stripe=stripe)

    assert report.cards[0].error == error
    assert not report.ok


def test_without_stripe_cards_and_requests_are_skipped() -> None:
    api = FakeApi()
    maya, priya = driver("Maya", plan(("mon",), time(8, 0))), rider("Priya")
    asks = (SeatRequestPlan(priya.email, maya.email, "to_campus", "accepted"),)

    report = run(api, maya, riders=(priya,), requests=asks)

    assert report.skipped_payments
    assert (report.cards, report.requests) == ([], [])
    assert api.setup_intents == []
    assert report.drivers[0].posted == 2  # trips still go up
    assert report.ok


def test_the_stripe_key_must_be_a_test_publishable_key() -> None:
    with pytest.raises(ValueError, match="pk_test_"):
        stripe_client("sk_test_123")
    with pytest.raises(ValueError, match="pk_test_"):
        stripe_client("pk_live_123")
    with stripe_client("pk_test_123") as client:
        assert client.base_url == httpx.URL("https://api.stripe.com")


# ---------------------------------------------------------------- #180: seat requests

MAYA = driver("Maya", plan(("mon", "wed"), time(8, 0)))
PRIYA = rider("Priya")
MAYAS_TRIPS = [  # as /trips/mine returns them
    trip("mon", "to_campus", "2025-10-27T13:00:00Z"),  # leaves in 2 hours: too soon to ask
    trip("wed", "to_campus", "2025-10-29T13:00:00Z"),
    trip("thu", "from_campus", "2025-10-30T21:00:00Z"),
]


def ask(status: Any = "accepted") -> tuple[SeatRequestPlan, ...]:
    return (SeatRequestPlan(PRIYA.email, MAYA.email, "to_campus", status),)


def test_the_rider_asks_for_the_next_trip_from_home_and_the_driver_accepts() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS})
    report = run(api, MAYA, riders=(PRIYA,), requests=ask(), stripe=FakeStripe())

    # 11:00 UTC Monday: Monday's 13:00 trip is under two hours away, so Wednesday's.
    assert api.asked == [(PRIYA.email, "wed", {"lat": 49.8722, "lng": -97.1561, "pickupId": "p1"})]
    assert api.detail_params == [{"lat": "49.8722", "lng": "-97.1561"}]
    assert api.accepted == [(MAYA.email, "r-wed")]
    assert report.requests == [
        RequestReport("Priya Test → Maya Test (to campus)", "accepted", created=True)
    ]


def test_a_pending_request_is_left_for_the_driver() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS})
    report = run(api, MAYA, riders=(PRIYA,), requests=ask("pending"), stripe=FakeStripe())

    assert len(api.asked) == 1
    assert api.accepted == []
    assert report.requests[0].status == "pending"


def test_a_request_already_there_isnt_made_again() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS})
    api.requests[PRIYA.email] = [
        {"trip": MAYAS_TRIPS[0], "request": {"id": "r-old", "status": "pending"}}
    ]

    report = run(api, MAYA, riders=(PRIYA,), requests=ask(), stripe=FakeStripe())

    assert api.asked == []
    assert api.accepted == [(MAYA.email, "r-old")]  # but accepted, as demo.json says
    assert report.requests[0] == RequestReport(
        "Priya Test → Maya Test (to campus)", "accepted", created=False
    )


def test_an_accepted_request_is_left_alone() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS})
    api.requests[PRIYA.email] = [
        {"trip": MAYAS_TRIPS[1], "request": {"id": "r-old", "status": "accepted"}}
    ]

    report = run(api, MAYA, riders=(PRIYA,), requests=ask(), stripe=FakeStripe())

    assert (api.asked, api.accepted) == ([], [])
    assert report.requests[0].status == "accepted"


def test_a_declined_request_doesnt_count() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS})
    api.requests[PRIYA.email] = [
        {"trip": MAYAS_TRIPS[1], "request": {"id": "r-old", "status": "declined"}}
    ]

    run(api, MAYA, riders=(PRIYA,), requests=ask(), stripe=FakeStripe())

    assert len(api.asked) == 1


def test_a_driver_with_no_trip_to_ask_for_is_reported() -> None:
    api = FakeApi(existing_trips={MAYA.email: MAYAS_TRIPS[:1]})  # only the one leaving soon

    report = run(api, MAYA, riders=(PRIYA,), requests=ask(), stripe=FakeStripe())

    assert report.requests[0].error == (
        "the driver has no upcoming trip that way; seed the trips first"
    )
    assert not report.ok


def test_main_prints_cards_requests_and_what_it_skipped(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
    report = SeedReport(
        drivers=[DriverReport("Aisha Okafor", posted=8, series=1)],
        cards=[
            CardReport("Priya Sharma", saved=True),
            CardReport("Noah Kim"),
            CardReport("Emma Roy", error="Stripe didn't save the test card (402)"),
        ],
        requests=[
            RequestReport("Priya Sharma → Maya Chen (to campus)", "accepted", created=True),
            RequestReport("Noah Kim → Maya Chen (to campus)", "pending"),
        ],
        skipped_payments=True,
    )
    monkeypatch.setattr(script, "seed_trips", lambda *args, **kwargs: report)

    assert main([]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "card     Priya Sharma: test Visa saved",
        "card     Noah Kim: already has a card",
        "FAILED   card for Emma Roy: Stripe didn't save the test card (402)",
        "posted   Aisha Okafor: 8 new trips (1 recurring series), 0 already there",
        "request  Priya Sharma → Maya Chen (to campus): new, accepted",
        "request  Noah Kim → Maya Chen (to campus): pending",
        "skipped  cards and seat requests: set STRIPE_PUBLISHABLE_KEY (pk_test_...) "
        "to the same Stripe sandbox as Payments",
    ]


def test_main_refuses_a_secret_stripe_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "sk_test_oops")

    assert main([]) == 1
    assert "pk_test_" in capsys.readouterr().err
