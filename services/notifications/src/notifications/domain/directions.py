"""Which way a trip goes (#355). It decides what the rider's point on the route is: going to
campus it's where they're picked up; leaving campus they're picked up on campus and it's
where they're dropped off."""

from enum import StrEnum


class TripDirection(StrEnum):
    TO_CAMPUS = "to_campus"
    FROM_CAMPUS = "from_campus"
