"""Rules for where a driver can pick a rider up (#28, #29)."""

# Roads a driver can't safely stop on to pick someone up: fast divided roads with no
# shoulder. A small list by name to start (#29), as OpenStreetMap names them (OSRM gives the
# road name of each point; checked against the Winnipeg map).
EXCLUDED_ROADS = frozenset(
    {
        # Bishop Grandin Boulevard, renamed Abinojii Mikanah in 2022: the map only has the
        # new name; the old one is kept for older map data.
        "abinojii mikanah",
        "bishop grandin boulevard",
        "kenaston boulevard",
        "perimeter highway",
    }
)

# Nothing within this straight-line distance of either end of a route is shown to riders:
# not a pickup point (#29), not the route on the map (#135). One end is campus; the other is
# the driver's own place, usually near home.
PRIVATE_END_METERS = 300

# Pickup points offered for one trip are at least this far apart along the route, so
# "choose a different point" (#136) offers a different spot, not the next 100 m sample.
MIN_PICKUP_SPACING_METERS = 200


def is_excluded_road(name: str) -> bool:
    return name.strip().casefold() in EXCLUDED_ROADS


def pickup_id(seq: int) -> str:
    """The opaque ID of a pickup point: which sample of the stored route it is. Trips sends
    it back when the rider requests a seat."""
    return f"s{seq}"
