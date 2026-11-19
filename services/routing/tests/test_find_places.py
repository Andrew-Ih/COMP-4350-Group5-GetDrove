"""Finding places by a typed address (#257): what the use case keeps and drops."""

from routing.application.find_places import FindPlaces
from routing.domain.places import MAP_AREA, MAX_PLACES, Area, Place, normalize_query
from routing.domain.values import LatLng

OSBORNE = Place("750 Osborne St, Fort Rouge", LatLng(49.8664, -97.1386))
POLO_PARK = Place("Polo Park, St. James", LatLng(49.8810, -97.2005))
TORONTO = Place("750 Osborne St, Toronto", LatLng(43.65, -79.38))


class FakeFinder:
    def __init__(self, places: list[Place]) -> None:
        self.places = places
        self.calls: list[tuple[str, Area, int]] = []

    async def find(self, query: str, area: Area, limit: int) -> list[Place]:
        self.calls.append((query, area, limit))
        return self.places


async def test_it_asks_for_the_map_area_and_at_most_five() -> None:
    finder = FakeFinder([OSBORNE])

    places = await FindPlaces(finder).execute("750 Osborne St")

    assert places == [OSBORNE]
    assert finder.calls == [("750 Osborne St", MAP_AREA, MAX_PLACES)]


async def test_places_outside_the_map_are_dropped() -> None:
    places = await FindPlaces(FakeFinder([TORONTO, POLO_PARK])).execute("polo")

    assert places == [POLO_PARK]


async def test_matches_with_the_same_label_keep_only_the_best() -> None:
    same_label = Place(OSBORNE.label, LatLng(49.8665, -97.1387))

    places = await FindPlaces(FakeFinder([OSBORNE, same_label, POLO_PARK])).execute("x x x")

    assert places == [OSBORNE, POLO_PARK]


async def test_nothing_found_is_an_empty_list() -> None:
    assert await FindPlaces(FakeFinder([])).execute("nowhere at all") == []


async def test_never_more_than_five() -> None:
    many = [Place(f"{n} Main St", LatLng(49.9 + n / 1000, -97.14)) for n in range(8)]

    assert len(await FindPlaces(FakeFinder(many)).execute("main st")) == MAX_PLACES


def test_the_map_area_is_the_osrm_bbox() -> None:
    """infra/osrm/Dockerfile: BBOX=-97.45,49.70,-96.85,50.05."""
    assert (MAP_AREA.west, MAP_AREA.south, MAP_AREA.east, MAP_AREA.north) == (
        -97.45,
        49.70,
        -96.85,
        50.05,
    )
    assert MAP_AREA.contains(LatLng(49.8075, -97.1366))  # campus
    assert not MAP_AREA.contains(LatLng(49.69, -97.14))  # just south of the map


def test_the_same_search_however_it_was_typed() -> None:
    assert normalize_query("  750   OSBORNE st ") == normalize_query("750 Osborne St")
