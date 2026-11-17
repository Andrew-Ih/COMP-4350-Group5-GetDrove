# Location privacy

> Back to [Architecture](architecture.md) · [Non-functional expectations](../product/non-functional.md)

Two locations in GetDrove are private (#31, story #28):

- **A rider's location.** Sent with every search and every pickup point request. It's used for that calculation only: it's never stored, never logged, and never shown to anyone, including drivers.
- **A driver's own place**, usually near home: the start of a trip to campus, or the end of a trip from campus. It's stored with the trip, but only that driver ever sees it.

What other people see instead is a **pickup point**: a point on the driver's route, labelled with a road name, never within 300 m (in a straight line) of either end of the route.

This page lists everywhere these locations pass through, the rule for each, and the test that proves it. It was written for the Sprint 2 audit (#31); update it when an endpoint or event that carries a place is added.

## Responses

| Where | Who gets it | Rule | Proven by |
|---|---|---|---|
| `GET /api/trips/search` | A rider | The driver's own end (`origin` going to campus, `destination` leaving it) is `null`. The rider's location isn't echoed back. | `trips/tests/test_search_trips_api.py` (`test_the_drivers_end_of_the_trip_is_private`), `trips/tests/test_location_privacy.py` |
| `GET /api/trips/{id}?lat=&lng=` (trip detail, #30) | Anyone logged in | The driver's own end is `null` for anyone but the driver. Pickup options come from Routing (so never near either end). `lat`/`lng` are only passed to Routing, never stored. | `trips/tests/test_trip_detail_api.py` (`test_a_rider_gets_the_trip_with_its_pickup_points`, `test_leaving_campus_the_drivers_end_is_hidden_too`, `test_the_driver_sees_their_own_end_and_no_pickups`) |
| `POST /api/trips/`, `GET /api/trips/mine` | The trip's driver | The driver's own trip, so their place is shown. Only their own trips are listed. | `trips/tests/test_location_privacy.py` (`test_the_driver_does_see_their_own_place`) |
| `POST /internal/matches`, `POST /internal/pickup-points` (Routing, called by Trips) | Trips, then the rider | Pickups are points on the route, never within 300 m of either end. The rider's location isn't echoed back. | `routing/tests/test_suggest_pickups.py`, `test_match_rider.py` (private ends), `routing/tests/test_location_privacy.py` |
| `GET /api/routing/trips/{id}/geometry` | Anyone logged in | Only the driver gets the whole route. Anyone else gets it with the driver's end cut off where it last leaves the 300 m circle around it (#135). Routes stored without a driver or direction have both ends cut off for everyone. | `routing/tests/test_privacy.py`, `routing/tests/test_route_geometry_api.py` |

Internal endpoints (`/api/<service>/internal/...`) are never exposed by the gateway (Traefik rules in `infra/docker-compose.yml` and `docker-compose.prod.yml`).

## Logs

| Where | Rule | Proven by |
|---|---|---|
| Each service's request log (`common_web`) | Logs the path only, never the query string (a search's query string holds the rider's location). | `routing/tests/test_location_privacy.py`, `trips/tests/test_location_privacy.py` (at `DEBUG`) |
| Outgoing HTTP calls (httpx) | OSRM takes coordinates in the URL, so httpx and httpcore only log warnings, whatever `LOG_LEVEL` is. | `common-web/tests/test_logs.py` (`test_outgoing_request_urls_are_not_logged`) |
| OSRM | Runs with `--verbosity WARNING`, so it doesn't log request URLs. | `infra/osrm/Dockerfile`; checked with `docker compose logs osrm-foot` |
| Every log line, every service | **Coordinates are taken out of every log line** (`common_web.logs`): any number with 4 or more decimals (a latitude or longitude to about 11 m) becomes `[coordinate]`, in the message, its arguments, any traceback and any `extra` field, in both the text and the JSON format (a redacted `extra` value becomes the string `"[coordinate]"`, so the JSON stays valid). The seconds of a time (`02:21:55.123456`) are left alone. **Added in #31.** | `common-web/tests/test_logs.py` (`test_logged_messages_and_tracebacks_never_contain_coordinates`, `test_extra_fields_never_contain_coordinates`) |
| Unexpected errors | Logged with their traceback, and error messages can quote a failed query's values: PostgreSQL and the database driver do (`invalid input for query argument $1: 'POINT(…)'`). The redaction above catches those. Trips' and Routing's database engines also use `hide_parameters`, so SQLAlchemy doesn't add the parameter list to the message. **Found and fixed in #31:** before, a database error mid-search would have logged the rider's exact location. | Routing: `test_a_database_failure_mid_search_logs_nothing_of_the_riders_location`. Trips: `test_a_database_failure_while_posting_logs_none_of_the_drivers_coordinates`. Both: `test_the_service_engine_doesnt_list_query_parameters_in_errors` |
| The gateway | Traefik's access log is off, locally and in production. | `infra/docker-compose.yml`, `docker-compose.prod.yml` (no `--accesslog`) |

Expected errors (404, 422, 503…) aren't logged, and validation errors don't echo the values sent.

The redaction only knows numbers: a place's **label** ("Driver's own street") would not be caught, so labels must never be logged either. Log IDs instead.

## Events

| Event | Place-related content |
|---|---|
| `TripPosted` | The trip ID only. Proven by `trips/tests/test_post_trip_api.py`. |
| `RequestAccepted` (seat requests, #34) | The pickup point's **label** (a road name), no coordinates. |
| Every other event | None. |

## Still to check

These don't exist yet. When they're built, they need the same rules and a test each:

- **Seat requests** (#137–#139, #142): the request stores the chosen **pickup point**, never the rider's location; the driver's list of requests shows only that pickup point.
- **Notifications** (emails and in-app, #144): reminders use the pickup label, never the rider's location or the driver's place.
