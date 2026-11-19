"""Nominatim (#257, ADR 0027): what Routing asks, how it reads the answer, and how it keeps
to the usage policy (1 request a second, cached, identified)."""

import asyncio
import itertools
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from routing.adapters.nominatim import (
    NominatimPlaceFinder,
    PoliteFinder,
    Throttle,
    _Result,
    label_for,
    purge_periodically,
)
from routing.domain.errors import GeocodingUnavailableError
from routing.domain.places import MAP_AREA, Area, Place
from routing.domain.values import LatLng

USER_AGENT = "GetDrove-test"
OSBORNE = {
    "lat": "49.8664",
    "lon": "-97.1386",
    "name": "",
    "display_name": "750, Osborne Street, Fort Rouge, Winnipeg, Manitoba, Canada",
    "address": {
        "house_number": "750",
        "road": "Osborne Street",
        "suburb": "Fort Rouge",
        "city": "Winnipeg",
    },
}
POLO_PARK = {
    "lat": "49.8810",
    "lon": "-97.2005",
    "name": "CF Polo Park",
    "display_name": "CF Polo Park, 1485, Portage Avenue, St. James, Winnipeg, Manitoba",
    "address": {"house_number": "1485", "road": "Portage Avenue", "city": "Winnipeg"},
}


def finder(handler: Callable[[httpx.Request], httpx.Response]) -> NominatimPlaceFinder:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://nominatim.test",
        headers={"User-Agent": USER_AGENT},
    )
    return NominatimPlaceFinder(client)


def answer(results: list[dict[str, Any]], seen: list[httpx.Request] | None = None) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=results)

    return handler


# ---------------------------------------------------------------- the request


async def test_it_asks_for_this_area_only_identifying_us() -> None:
    seen: list[httpx.Request] = []

    await finder(answer([], seen)).find("750 Osborne St", MAP_AREA, 5)

    [request] = seen
    assert request.url.path == "/search"
    assert dict(request.url.params) == {
        "q": "750 Osborne St",
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": "5",
        "countrycodes": "ca",
        "viewbox": "-97.45,50.05,-96.85,49.7",  # left, top, right, bottom
        "bounded": "1",
        "accept-language": "en",
    }
    assert request.headers["User-Agent"] == USER_AGENT


async def test_it_reads_each_match() -> None:
    places = await finder(answer([OSBORNE, POLO_PARK])).find("x", MAP_AREA, 5)

    assert places == [
        Place("750 Osborne Street, Fort Rouge", LatLng(49.8664, -97.1386)),
        Place("1485 Portage Avenue, Winnipeg", LatLng(49.8810, -97.2005)),
    ]


async def test_no_match_is_an_empty_list() -> None:
    assert await finder(answer([])).find("nowhere", MAP_AREA, 5) == []


# ---------------------------------------------------------------- labels


@pytest.mark.parametrize(
    ("result", "label"),
    [
        (OSBORNE, "750 Osborne Street, Fort Rouge"),
        (
            {"lat": 1, "lon": 1, "name": "Assiniboine Park", "address": {"suburb": "Tuxedo"}},
            "Assiniboine Park, Tuxedo",
        ),
        (
            {"lat": 1, "lon": 1, "address": {"road": "Pembina Highway", "city": "Winnipeg"}},
            "Pembina Highway, Winnipeg",
        ),
        ({"lat": 1, "lon": 1, "name": "Winnipeg", "address": {"city": "Winnipeg"}}, "Winnipeg"),
        ({"lat": 1, "lon": 1, "display_name": "Somewhere, Manitoba"}, "Somewhere"),
    ],
)
def test_labels_are_short(result: dict[str, Any], label: str) -> None:
    assert label_for(_Result.model_validate(result)) == label


# ---------------------------------------------------------------- failures


def down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


def slow(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        down,
        slow,
        lambda r: httpx.Response(503, text="Service unavailable"),
        lambda r: httpx.Response(429, text="Too many requests"),
        lambda r: httpx.Response(403, text="Blocked"),
        lambda r: httpx.Response(200, content=b"<html>not json</html>"),
        lambda r: httpx.Response(200, json={"error": "Unable to geocode"}),
        lambda r: httpx.Response(200, json=[{"lat": "north", "lon": "-97"}]),
    ],
    ids=["down", "timeout", "503", "rate-limited", "blocked", "html", "error-object", "bad-lat"],
)
async def test_any_failure_is_geocoding_unavailable(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    with pytest.raises(GeocodingUnavailableError) as caught:
        await finder(handler).find("750 Osborne St", MAP_AREA, 5)

    assert caught.value.status == 503
    assert caught.value.code == "geocoding_unavailable"


# ---------------------------------------------------------------- the throttle


class FakeTime:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


async def test_calls_are_spaced_one_second_apart() -> None:
    time = FakeTime()
    throttle = Throttle(min_interval=1.0, max_wait=3.0, clock=time.clock, sleep=time.sleep)

    await throttle.wait_turn()  # first: straight away
    await throttle.wait_turn()  # second: waits a second
    time.now += 5
    await throttle.wait_turn()  # long after: straight away

    assert time.slept == [1.0]


class LateTime(FakeTime):
    """A clock whose sleeps yield to other tasks and can wake up late, like a busy server."""

    def __init__(self, late_by: float = 0.0) -> None:
        super().__init__()
        self.late_by = late_by

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        await asyncio.sleep(0)  # let the other callers run, as a real sleep does
        self.now += seconds + self.late_by


async def let_through(throttle: Throttle, time: FakeTime, starts: list[float]) -> None:
    await throttle.wait_turn()
    starts.append(time.now)  # when this caller may send its request


async def test_callers_arriving_together_go_one_second_apart() -> None:
    time = LateTime()
    throttle = Throttle(min_interval=1.0, max_wait=5.0, clock=time.clock, sleep=time.sleep)
    starts: list[float] = []

    await asyncio.gather(*(let_through(throttle, time, starts) for _ in range(3)))

    assert starts == [100.0, 101.0, 102.0]


async def test_late_wakeups_never_let_two_through_together() -> None:
    """Chimdi's case: sleeps that wake 1.5 s late released callers at the same moment."""
    time = LateTime(late_by=1.5)
    throttle = Throttle(min_interval=1.0, max_wait=10.0, clock=time.clock, sleep=time.sleep)
    starts: list[float] = []

    await asyncio.gather(*(let_through(throttle, time, starts) for _ in range(3)))

    assert len(starts) == 3
    gaps = [later - earlier for earlier, later in itertools.pairwise(starts)]
    assert all(gap >= 1.0 for gap in gaps), starts


async def test_a_long_queue_is_turned_away_rather_than_kept_waiting() -> None:
    time = LateTime()
    throttle = Throttle(min_interval=1.0, max_wait=2.0, clock=time.clock, sleep=time.sleep)
    starts: list[float] = []

    results = await asyncio.gather(
        *(let_through(throttle, time, starts) for _ in range(4)), return_exceptions=True
    )

    assert starts == [100.0, 101.0, 102.0]  # waits of 0, 1 and 2 seconds
    assert [type(r) for r in results].count(GeocodingUnavailableError) == 1  # 3 would be too long


# ---------------------------------------------------------------- the cache


class CountingFinder:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    async def find(self, query: str, area: Area, limit: int) -> list[Place]:
        self.calls.append(query)
        if self.fail:
            raise GeocodingUnavailableError()
        return [Place(query, LatLng(49.88, -97.14))]


def polite(inner: CountingFinder, time: FakeTime, max_entries: int = 3) -> PoliteFinder:
    throttle = Throttle(min_interval=1.0, max_wait=3.0, clock=time.clock, sleep=time.sleep)
    return PoliteFinder(inner, throttle, ttl_seconds=60, max_entries=max_entries, clock=time.clock)


async def test_a_repeated_search_is_answered_from_memory() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time)

    first = await places.find("750 Osborne St", MAP_AREA, 5)
    again = await places.find("  750 osborne   ST ", MAP_AREA, 5)

    assert again == first
    assert inner.calls == ["750 Osborne St"]
    assert time.slept == []  # and doesn't wait its turn


async def test_cached_answers_expire() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time)

    await places.find("Polo Park", MAP_AREA, 5)
    time.now += 61
    await places.find("Polo Park", MAP_AREA, 5)

    assert inner.calls == ["Polo Park", "Polo Park"]


async def test_the_cache_keeps_only_the_latest_searches() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time, max_entries=2)

    for query in ("one", "two", "three", "one"):
        await places.find(query, MAP_AREA, 5)

    assert inner.calls == ["one", "two", "three", "one"]  # "one" was pushed out


async def test_expired_searches_are_removed_from_memory_on_the_next_search() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time)
    await places.find("750 Osborne St", MAP_AREA, 5)
    time.now += 2 * 3600

    await places.find("Polo Park", MAP_AREA, 5)

    assert [key[0] for key in places._cache] == ["polo park"]  # the address is gone


async def test_expired_searches_are_removed_while_no_one_searches() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time)
    await places.find("750 Osborne St", MAP_AREA, 5)
    await places.find("Polo Park", MAP_AREA, 5)
    time.now += 61

    assert places.purge_expired() == 2
    assert places._cache == {}


async def test_the_timer_purges_until_stopped() -> None:
    inner, time = CountingFinder(), FakeTime()
    places = polite(inner, time)
    await places.find("750 Osborne St", MAP_AREA, 5)
    time.now += 61
    stop = asyncio.Event()

    task = asyncio.create_task(purge_periodically(places, stop, interval_seconds=0.01))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1)

    assert places._cache == {}


async def test_failures_arent_cached() -> None:
    inner, time = CountingFinder(fail=True), FakeTime()
    places = polite(inner, time)

    for _ in range(2):
        with pytest.raises(GeocodingUnavailableError):
            await places.find("Polo Park", MAP_AREA, 5)

    assert inner.calls == ["Polo Park", "Polo Park"]


async def test_a_cached_answer_cant_be_changed_by_the_caller() -> None:
    places = polite(CountingFinder(), FakeTime())

    first = await places.find("Polo Park", MAP_AREA, 5)
    first.clear()

    assert await places.find("Polo Park", MAP_AREA, 5) != []
