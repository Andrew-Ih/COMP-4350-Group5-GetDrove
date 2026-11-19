"""Finds places with OpenStreetMap's Nominatim (ADR 0027, #257).

Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/): searches
people trigger themselves, at most 1 request a second for the whole application, an
identifying User-Agent (set on the HTTP client), results cached, and OpenStreetMap credited
(the map already does). No autocomplete. API: https://nominatim.org/release-docs/latest/api/Search/

What was typed goes in Nominatim's query string, but never in our logs: the services don't log
httpx's request URLs (common_web), and nothing here logs the query.
"""

import asyncio
import contextlib
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from routing.application.ports import PlaceFinder
from routing.domain.errors import GeocodingUnavailableError
from routing.domain.places import Area, Place, normalize_query
from routing.domain.values import LatLng

# Address parts that name the area around a place, most specific first, for its label.
AREA_PARTS = ("neighbourhood", "suburb", "quarter", "city_district", "city", "town", "village")
MAX_LABEL_LENGTH = 120


class _Address(BaseModel):
    house_number: str | None = None
    road: str | None = None
    neighbourhood: str | None = None
    suburb: str | None = None
    quarter: str | None = None
    city_district: str | None = None
    city: str | None = None
    town: str | None = None
    village: str | None = None


class _Result(BaseModel):
    lat: float
    lon: float
    name: str | None = None
    display_name: str = ""
    address: _Address = _Address()


_RESULTS = TypeAdapter(list[_Result])


def label_for(result: "_Result") -> str:
    """`750 Osborne St, Fort Rouge` for an address, `Polo Park, St. James` for a place."""
    address = result.address
    if address.house_number and address.road:
        main = f"{address.house_number} {address.road}"
    else:
        main = result.name or address.road or result.display_name.split(",")[0]
    main = main.strip()
    around = next(
        (part for key in AREA_PARTS if (part := getattr(address, key)) and part != main), None
    )
    label = f"{main}, {around}" if around else main
    return label[:MAX_LABEL_LENGTH]


class NominatimPlaceFinder:
    """``client`` points at Nominatim and sends our User-Agent (infrastructure/main.py)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def find(self, query: str, area: Area, limit: int) -> list[Place]:
        try:
            response = await self.client.get(
                "/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": limit,
                    "countrycodes": "ca",
                    # Only inside the area: left,top,right,bottom.
                    "viewbox": f"{area.west},{area.north},{area.east},{area.south}",
                    "bounded": 1,
                    "accept-language": "en",
                },
            )
            response.raise_for_status()
            results = _RESULTS.validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise GeocodingUnavailableError() from exc
        return [
            Place(label=label_for(result), point=LatLng(lat=result.lat, lng=result.lon))
            for result in results
        ]


Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]


class Throttle:
    """Spaces calls at least ``min_interval`` seconds apart for the whole service, measured
    between the moments callers are let through. A caller that would have to wait longer than
    ``max_wait`` is turned away (GeocodingUnavailableError) instead of keeping someone waiting.

    Callers go through one at a time, holding a lock while they wait, and the clock is read
    again after every sleep: a sleep can wake late, and late wakeups must never let two
    callers through together (Nominatim's limit is an absolute maximum).
    """

    def __init__(
        self,
        min_interval: float,
        max_wait: float,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.min_interval = min_interval
        self.max_wait = max_wait
        self.clock = clock
        self.sleep = sleep
        self._lock = asyncio.Lock()
        self._last_start = float("-inf")
        self._queued = 0  # callers waiting for their turn, including the one holding the lock

    def _wait_now(self) -> float:
        return max(0.0, self._last_start + self.min_interval - self.clock())

    async def wait_turn(self) -> None:
        # Turned away at once if the callers already waiting would take us past max_wait.
        if self._queued * self.min_interval + self._wait_now() > self.max_wait:
            raise GeocodingUnavailableError()
        deadline = self.clock() + self.max_wait
        self._queued += 1
        try:
            async with self._lock:
                while (wait := self._wait_now()) > 0:
                    if self.clock() + wait > deadline:
                        raise GeocodingUnavailableError()
                    await self.sleep(wait)
                # No await between the check above and this: the next caller measures from here.
                self._last_start = self.clock()
        finally:
            self._queued -= 1


class PoliteFinder:
    """Nominatim as its policy asks: repeated searches answered from memory, and the rest
    spaced out by ``throttle``.

    The cache holds what was typed only in this process's memory, for ``ttl_seconds`` at most,
    and at most ``max_entries`` searches; it's never written anywhere. Expired searches are
    removed on every search, and by ``purge_expired``, which the service also runs on a timer
    so nothing outlives its hour while no one is searching. Failures aren't cached.
    """

    def __init__(
        self,
        inner: PlaceFinder,
        throttle: Throttle,
        ttl_seconds: float,
        max_entries: int,
        clock: Clock = time.monotonic,
    ) -> None:
        self.inner = inner
        self.throttle = throttle
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self._cache: OrderedDict[tuple[str, Area, int], tuple[float, list[Place]]] = OrderedDict()

    def purge_expired(self) -> int:
        """Removes every expired search from memory. Returns how many were removed."""
        now = self.clock()
        expired = [key for key, (expires, _) in self._cache.items() if expires <= now]
        for key in expired:
            del self._cache[key]
        return len(expired)

    async def find(self, query: str, area: Area, limit: int) -> list[Place]:
        self.purge_expired()
        key = (normalize_query(query), area, limit)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return list(cached[1])
        await self.throttle.wait_turn()
        places = await self.inner.find(query, area, limit)
        self._cache[key] = (self.clock() + self.ttl_seconds, places)
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return list(places)


async def purge_periodically(
    finder: PoliteFinder, stop: asyncio.Event, interval_seconds: float = 60.0
) -> None:
    """Removes expired searches every ``interval_seconds`` until ``stop`` is set, so a typed
    address never stays in memory much past its hour, even when no one searches again."""
    while not stop.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        finder.purge_expired()
