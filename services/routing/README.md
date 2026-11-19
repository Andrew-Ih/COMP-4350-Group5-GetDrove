# Routing service

**Owner:** Rayan

Driving routes via OSRM, corridor matching, pickup points, detours, pickup ordering and ETAs.

## Run locally

From the repo root:

```bash
uv sync
uv run --package routing uvicorn routing.infrastructure.main:app --reload --port 8003
```

Then open http://localhost:8003/health and the API docs at http://localhost:8003/docs.

Computing a route needs OSRM running. Without it, `POST /internal/routes` answers 503. See [infra/osrm/README.md](../../infra/osrm/README.md) to prepare the map data once, then `docker compose --profile osrm up -d`.

## Test and check

```bash
uv run pytest services/routing
uv run mypy services/routing/src
cd services/routing && uv run lint-imports
```

The repository and API tests use a real PostgreSQL database with PostGIS. With Docker running, they start their own throwaway one (testcontainers, the `routing_database` fixture in `tests/conftest.py`) with the real migrations applied, so there's nothing to set up; without Docker they're skipped with a message. OSRM is always mocked in tests.

## Database migrations

Tables live in the `routing` Postgres schema. With the database running and `ROUTING_DATABASE_URL` set:

```bash
cd services/routing
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/routing/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/routing/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/routing/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/routing/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

The OpenAPI spec is [contracts/openapi/routing.json](../../contracts/openapi/routing.json).

### Computing a trip's route (#24)

`POST /internal/routes` is called by Trips when a driver posts a trip. It's internal: only reachable inside Docker (`http://routing:8000/internal/routes`), never through the gateway.

1. Asks OSRM's car profile for the driving route between the origin and the destination.
2. Stores the full route in `routing.routes` as a PostGIS `LINESTRING` (SRID 4326, `[lng lat]` order), with its distance and duration. A GiST index on `path` is there for matching (#25, #26). It also stores the `driverId` and `direction` Trips sends (#135), which decide who sees the whole route on the map. Both are optional: routes stored without them have both ends hidden from everyone.
3. Returns the distance in meters and the duration in seconds, rounded to whole numbers.

Calling it again for the same trip replaces that trip's route. Errors:

| Status | Code | When |
|---|---|---|
| 422 | `invalid_input` | Bad coordinates, a point more than 500 m from a road on the map (so anywhere outside Winnipeg), or no road route between the points (OSRM's `NoSegment`, `NoRoute`) |
| 503 | `routing_engine_unavailable` | OSRM is down, errors, returns something unexpected, or takes longer than `ROUTING_OSRM_TIMEOUT_SECONDS` (default 2.5) |

Nothing is stored when a request fails.

### The corridor around each route (#25)

When a route is stored, points every 100 m along it are stored too, in `routing.route_samples` (a PostGIS geography `POINT` with a GiST index). Each sample knows how far into the drive it is (`offset_meters`, `offset_seconds`, scaled to OSRM's distance and duration), so a rider picked up there rides `distance_meters - offset_meters`. Samples are replaced with their route and deleted with it.

The corridor is the area within `ROUTING_CORRIDOR_METERS` (default 800) of a route, in a straight line. `SQLAlchemyRouteRepository.samples_in_corridor` finds, for a rider and the candidate trips Trips sends, the samples inside it, nearest first. It's only a quick first pass: a rider across the river from a route can be well inside the corridor, so matching (#26) then checks the real walking time to these samples with OSRM's foot profile.

### Choosing pickup points (#26, #29)

Search (`/internal/matches`) and the pickup points endpoint choose points the same way (`application/pickups.py`), so a trip's first suggested point is the one search showed for the same rider and spot.

1. **Corridor:** the samples of the trip's route within `ROUTING_CORRIDOR_METERS` of the rider (#25), the 20 nearest per trip.
2. **Never near either end:** samples within 300 m of either end of the route, in a straight line, are skipped. One end is campus; the other is the driver's own place, usually near home, and a pickup pin a few meters from it would give it away.
3. **Walking check:** one OSRM foot `table` request (split into chunks of 99, OSRM's limit, sent at once) gives the walking time from the rider to each sample. Only samples within `ROUTING_MAX_WALK_SECONDS` (default 600, about 830 m at OSRM's 5 km/h) count. This is what leaves out a rider across the river from a route: close in a straight line, but a long walk round to a bridge.
4. **Shortest walk first**, skipping:
   - points on **roads a driver can't safely stop on** (`domain/pickups.py`): Abinojii Mikanah (formerly Bishop Grandin Boulevard; the map only has the new name), Kenaston Boulevard and the Perimeter Highway;
   - points within **200 m along the route** of one already chosen, so the next suggestion is a different spot.

Each point is labelled with the nearest named road within 150 m, from OSRM's car profile (`nearest`, 20 candidates, since the closest are often unnamed service roads or parking lot aisles), or "a spot on the driver's route" if there's none or the lookup fails. That lookup is also how excluded roads are recognised, so **excluded roads fail open**: if the car profile is down while the foot profile is up, the lookup returns no name, nothing is excluded, and a point on, say, Kenaston Boulevard can be offered as "a spot on the driver's route". Both profiles run on the same server, so this should be rare.

A rider who's only near an end of a route, only near excluded roads, or can't walk to it, gets no point for that trip. Going to campus, the point is where the rider is picked up; leaving campus, where they're dropped off. `riderDistanceMeters` is always the rest of the route from that point to the trip's end; Trips knows the direction and works out how far the rider rides. The rider's location is used for the calculation only, never stored or logged.

### Matching a rider to trips (#26)

`POST /internal/matches` is called by Trips' search (#97) with the rider's location and the candidate trips (already filtered by time, seats and status). It's internal, like `/internal/routes`. A trip matches if it has a pickup point for this rider (above); its best one is returned. Matches come back in the order of `tripIds`; trips that don't match are left out, and an empty list is a normal result. If the foot profile is down, the answer is 503 `routing_engine_unavailable`.

### Pickup points for a trip (#29)

`POST /internal/pickup-points` is called by Trips for the trip detail and when a seat is requested, with a trip, the rider's location and a `limit` (default 3, at most 5). It returns up to `limit` points chosen as above, shortest walk first, each with:

- `id`: which sample of the stored route it is (e.g. `s42`). Trips sends it back when the rider requests a seat.
- `label`, `lat`, `lng`, `walkSeconds`, and `riderDistanceMeters` (as in matches).

**Rejected points:** `exclude` takes up to 20 IDs of points the rider turned down ("choose a different pickup point", #136). They're never returned, so the next best come back instead. Rejected points still count for the 200 m spacing, so the next suggestion is a different spot, not the sample next door. Unknown IDs are ignored. Rejecting every point leaves an empty list.

An empty list means the route doesn't pass within walking distance (or every point there was rejected). 404 `route_not_found` if the trip has no stored route (checked before calling OSRM), 503 `routing_engine_unavailable` if the foot profile is down.

### Extra driving time for a new pickup (#36, #38)

`POST /internal/detours` is called by Trips when a seat is requested, with a trip, the pickups of the riders already accepted (in pickup order, at most 6) and the new pickup. It returns how much driving time the new pickup adds to the trip, at its best place among the accepted ones.

1. **One OSRM request:** a car `table` request gives the drive time between every pair of the trip's start, the accepted pickups, the new pickup and the trip's end. The start and end are the first and last points of the stored route.
2. **Cheapest insertion** (`domain/insertion.py`, #38): the new pickup is tried at every position and the one that adds the least time wins. On a tie, the earliest position wins. The added time is never negative.
3. **The answer:** `addedSeconds`, `position` (how many accepted pickups come before it, 0 = first) and `totalSeconds` (the trip as it stands plus `addedSeconds`), all in whole seconds.

It fails fast, because Trips calls it while the rider waits. The call to OSRM waits at most `ROUTING_DETOUR_TIMEOUT_SECONDS` (default 0.8; the other endpoints use `ROUTING_OSRM_TIMEOUT_SECONDS`, 2.5). A pair of points with no route between them is a 503 as well: a detour worked out from a guess would be a wrong number.

| Status | Code | When |
|---|---|---|
| 404 | `route_not_found` | The trip has no stored route (checked before calling OSRM) |
| 422 | `invalid_input` | Bad coordinates, or more than 6 accepted pickups |
| 503 | `routing_engine_unavailable` | OSRM is down, errors, returns something unexpected, has no route between two of the points, or takes longer than `ROUTING_DETOUR_TIMEOUT_SECONDS` |

### A trip's route for the map (#123, #135)

`GET /trips/{tripId}/geometry` (gateway: `GET /api/routing/trips/{tripId}/geometry`) returns the route as a GeoJSON `Feature` with a `LineString`, which MapLibre draws as is. Coordinates are `[lng, lat]` pairs; `properties` has the trip ID, and the whole trip's distance and duration. The driver's screen after posting a trip and the rider's search results both use it.

**Only the driver sees the whole route** (`domain/privacy.py`). Anyone else gets it with the driver's own end cut off: the start going to campus, the end leaving it. The cut is where the route last leaves a 300 m circle (straight line) around that end, the same margin pickup points keep, so a route that loops back past the house from a cul-de-sac is cut after the loop, not before. The campus end is always drawn. Routes stored without a driver or direction (before Sprint 2) have both ends cut off, for everyone. A route entirely inside the circle shows only its far end, as a line of no length.

It needs a logged-in user (401 otherwise), returns 404 `route_not_found` for a trip with no route, and 422 for an ID that isn't a UUID.

### Finding a place by its address (#257, ADR 0027)

`POST /places` (gateway: `POST /api/routing/places`) with `{ "query": "750 Osborne St" }` lets riders and drivers choose their area by typing instead of tapping the map. It returns up to 5 `{ label, lat, lng }` matches inside the map's area (the OSRM `BBOX`), best first, or an empty list.

It asks OpenStreetMap's public geocoder, [Nominatim](https://nominatim.org/release-docs/latest/api/Search/), keeping to its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) (`adapters/nominatim.py`):

- **Bounded to Winnipeg:** `viewbox` with `bounded=1`, Canada only, and the use case drops anything outside the map anyway.
- **At most 1 request a second** for the whole service (`ROUTING_GEOCODER_MIN_INTERVAL_SECONDS`), measured between the moments requests are sent: callers go through one at a time and the clock is read again after every wait, so a late wakeup never lets two through together. A search that would wait longer than `ROUTING_GEOCODER_MAX_WAIT_SECONDS` (3) is answered 503 instead.
- **Cached:** the same search again (spaces and case ignored) is answered from memory for an hour, up to 500 searches (`ROUTING_PLACES_CACHE_TTL_SECONDS`, `ROUTING_PLACES_CACHE_MAX_ENTRIES`). Expired searches are removed on every search and once a minute, so a typed address doesn't stay in memory past its hour while no one searches. Failures aren't cached.
- **Identified:** every request sends `ROUTING_GEOCODER_USER_AGENT`.
- **Private:** a POST, so the address is never in one of our URLs, and nothing logs it. The cache lives only in the process's memory.

Locally it calls the real Nominatim too (`ROUTING_GEOCODER_URL`), so it needs internet access; the tests use fakes.

| Status | Code | When |
|---|---|---|
| 401 | `unauthorized` | No valid access token |
| 422 | `invalid_input` | `query` shorter than 3 or longer than 200 characters (after trimming) |
| 503 | `geocoding_unavailable` | Nominatim is down, errors, is too slow (`ROUTING_GEOCODER_TIMEOUT_SECONDS`, 3), answers something unexpected, or too many searches are waiting |

## Events

_Published and consumed events, linking to `contracts/events/`._
