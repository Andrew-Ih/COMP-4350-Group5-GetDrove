# OSRM: the routing engine

OSRM works out driving routes, walking times and the nearest road to a point, from OpenStreetMap data ([ADR 0008](../../docs/architecture/adr/0008-routing-engine.md)). The Routing service calls it; nothing else does. Two instances run, one per profile:

| Instance | Used for | Inside Docker | From your machine |
|---|---|---|---|
| `osrm-car` | Driving routes and times (a driver's route), road names for pickups | `http://osrm-car:5000` | `http://localhost:5050` |
| `osrm-foot` | Walking times (rider to pickup point) | `http://osrm-foot:5000` | `http://localhost:5051` |

The Routing service reads these as `ROUTING_OSRM_CAR_URL` and `ROUTING_OSRM_FOOT_URL`.

The ports on your machine are 5050 and 5051, not 5000, because macOS uses port 5000 for AirPlay Receiver. To use other ports, set `OSRM_CAR_PORT` / `OSRM_FOOT_PORT` and point `ROUTING_OSRM_CAR_URL` / `ROUTING_OSRM_FOOT_URL` at them.

## How the map gets in

[`Dockerfile`](Dockerfile) builds an image with the map inside, so there's nothing to prepare by hand:

1. Downloads the Manitoba extract from [Geofabrik](https://download.geofabrik.de/north-america/canada/manitoba.html) (about 200 MB).
2. Clips it to Winnipeg and the area around the Perimeter Highway (`osmium extract`).
3. Builds the graph for one profile (`PROFILE=car` or `PROFILE=foot`) with MLD.
4. The final image is just OSRM and that graph.

The same Dockerfile is used locally (Docker Compose builds it) and for the live server (the deploy workflow builds it in GitHub Actions and the server pulls it). Steps 1–3 are cached by Docker, so they only run again when the Dockerfile changes.

## Run it locally

OSRM is part of the normal stack:

```bash
docker compose up --build -d
bash infra/osrm/check.sh
```

The **first build downloads the map and takes a few minutes**; after that it's cached and starts in seconds. `check.sh` asks both instances for a route from Osborne Village to University Centre and prints the distance and time (about 9 km).

To run only OSRM (for example, with the Routing service running outside Docker): `docker compose up --build -d osrm-car osrm-foot`.

Try it yourself: `curl "http://localhost:5050/route/v1/driving/-97.1438,49.8768;-97.1366,49.8075?overview=false"`. OSRM takes coordinates as `longitude,latitude`. Its API is documented at <https://project-osrm.org/docs/v5.24.0/api/>.

## Logging

The image runs `osrm-routed --verbosity WARNING`. At OSRM's default (`INFO`) it logs every request's URL, and the URL holds the coordinates of riders and drivers, which must never be stored. For the same reason, the services don't log httpx's request URLs (`common_web.configure_logging`).

## Updating the map

- **Locally:** `docker compose build --no-cache osrm-car osrm-foot`, then `docker compose up -d osrm-car osrm-foot`.
- **Live server:** **Actions → Deploy → Run workflow** from `main` with **refresh_map** ticked ([Deployment](../../docs/deployment/deployment.md#routing-engine-osrm)).

## Settings

Build arguments of the Dockerfile, all optional except `PROFILE`:

| Argument | Default | What |
|---|---|---|
| `PROFILE` | (required) | `car` or `foot` |
| `OSRM_VERSION` | `v5.27.1` | OSRM image version |
| `EXTRACT_URL` | Geofabrik's Manitoba extract | Where to download the map from |
| `BBOX` | `-97.45,49.70,-96.85,50.05` | Area kept: west, south, east, north |
| `MAP_REFRESH` | `cached` | Any new value downloads the map again instead of using the cached one |
