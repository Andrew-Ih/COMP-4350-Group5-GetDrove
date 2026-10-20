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
2. Stores the full route in `routing.routes` as a PostGIS `LINESTRING` (SRID 4326, `[lng lat]` order), with its distance and duration. A GiST index on `path` is there for matching (#25, #26).
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

### Matching a rider to trips (#26)

`POST /internal/matches` is called by Trips' search (#97) with the rider's location and the candidate trips (already filtered by time, seats and status). It's internal, like `/internal/routes`.

1. **Corridor:** the samples of those trips' routes within `ROUTING_CORRIDOR_METERS` of the rider (#25), the 20 nearest per trip.
2. **Walking check:** one OSRM foot `table` request (split into chunks of 99, OSRM's limit) gives the walking time from the rider to each sample. A trip matches only if some sample is within `ROUTING_MAX_WALK_SECONDS` (default 600, about 830 m at OSRM's 5 km/h). This is what leaves out a rider across the river from a route: close in a straight line, but a long walk round to a bridge.
3. **Pickup:** per matching trip, the sample with the shortest walk. It's on the driver's route, so the driver can stop there. Its label is the nearest named road within 150 m, from OSRM's car profile (`nearest`, 20 candidates, since the closest are often unnamed service roads or parking lot aisles), or "a spot on the driver's route" if there's none or the lookup fails.

**The ends of a route are never offered.** Samples within 300 m of either end are skipped. One end is campus; the other is the driver's own place, usually near home, and a pickup pin a few meters from it would give it away. A rider who's only near an end gets no match for that trip.

Going to campus, the point is where the rider is picked up; leaving campus, where they're dropped off. `riderDistanceMeters` is always the rest of the route from that point to the trip's end; Trips knows the direction and works out how far the rider rides. Matches come back in the order of `tripIds`; trips that don't match are left out, and an empty list is a normal result. If the foot profile is down, the answer is 503 `routing_engine_unavailable`. The rider's location is used for the calculation only, never stored or logged.

### A trip's route for the map (#123)

`GET /trips/{tripId}/geometry` (gateway: `GET /api/routing/trips/{tripId}/geometry`) returns the stored route as a GeoJSON `Feature` with a `LineString`, which MapLibre draws as is. Coordinates are `[lng, lat]` pairs, exactly as stored; `properties` has the trip ID, distance and duration. The driver's screen after posting a trip and the rider's search results both use it.

It needs a logged-in user (401 otherwise), returns 404 `route_not_found` for a trip with no route, and 422 for an ID that isn't a UUID.

In Sprint 1, any logged-in user gets the full route, including the driver's starting point. From Sprint 2, riders get the route from their pickup point on, so the driver's start stays private.

## Events

_Published and consumed events, linking to `contracts/events/`._
