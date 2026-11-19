"""Use case: find the places matching an address someone typed (#257, ADR 0027).

What was typed is only passed on to the place finder. It's never stored, and never logged.
"""

from routing.application.ports import PlaceFinder
from routing.domain.places import MAP_AREA, MAX_PLACES, Area, Place


class FindPlaces:
    def __init__(self, finder: PlaceFinder, area: Area = MAP_AREA) -> None:
        self.finder = finder
        self.area = area

    async def execute(self, query: str) -> list[Place]:
        found = await self.finder.find(query, self.area, MAX_PLACES)
        places: list[Place] = []
        labels: set[str] = set()
        for place in found:
            # The finder is asked for this area only, but a match must be somewhere we can route
            # to, so check rather than trust it. Two matches with the same label can't be told
            # apart, so only the best is kept.
            if not self.area.contains(place.point) or place.label in labels:
                continue
            labels.add(place.label)
            places.append(place)
        return places[:MAX_PLACES]
