# OSRM: the routing engine

OSRM works out driving routes, walking times and the nearest road to a point, from OpenStreetMap data ([ADR 0008](../../docs/architecture/adr/0008-routing-engine.md)). The Routing service calls it; nothing else does. Two instances run, one per profile:

| Instance | Used for | Inside Docker | From your machine |
|---|---|---|---|
| `osrm-car` | Driving routes and times (a driver's route, detours) | `http://osrm-car:5000` | `http://localhost:5050` |
| `osrm-foot` | Walking times (rider to pickup point) | `http://osrm-foot:5000` | `http://localhost:5051` |

The Routing service reads these as `ROUTING_OSRM_CAR_URL` and `ROUTING_OSRM_FOOT_URL`.

The ports on your machine are 5050 and 5051, not 5000, because macOS uses port 5000 for AirPlay Receiver. To use other ports, set `OSRM_CAR_PORT` / `OSRM_FOOT_PORT` and point `ROUTING_OSRM_CAR_URL` / `ROUTING_OSRM_FOOT_URL` at them.

## Set it up (once)

The map data isn't in the repo, so prepare it first. Start Docker first. It downloads about 200 MB, needs about 1 GB of free disk, and takes a few minutes:

```bash
bash infra/osrm/prepare.sh
```

This downloads the Manitoba extract from [Geofabrik](https://download.geofabrik.de/north-america/canada/manitoba.html), clips it to Winnipeg and the area around the Perimeter Highway, and builds the car and foot graphs into `infra/osrm/data/` (gitignored).

## Run it

OSRM is behind a Compose profile, so `docker compose up` keeps working for anyone who hasn't prepared the data:

```bash
docker compose --profile osrm up -d
bash infra/osrm/check.sh
```

`check.sh` asks both instances for a route from Osborne Village to University Centre and prints the distance and time (about 9–10 km).

Try it yourself: `curl "http://localhost:5050/route/v1/driving/-97.1438,49.8768;-97.1366,49.8075?overview=false"`. OSRM takes coordinates as `longitude,latitude`. Its API is documented at <https://project-osrm.org/docs/v5.24.0/api/>.

## Updating the map

Run `prepare.sh` again: it rebuilds the graphs from the extract already downloaded. Delete `infra/osrm/data/manitoba-latest.osm.pbf` first to download newer map data. Restart the two containers afterwards.

## Settings

`prepare.sh` reads these environment variables, all optional:

| Variable | Default | What |
|---|---|---|
| `OSRM_IMAGE` | `ghcr.io/project-osrm/osrm-backend:v5.27.1` | OSRM version (keep it the same as in `docker-compose.yml`) |
| `EXTRACT_URL` | Geofabrik's Manitoba extract | Where to download the map from |
| `BBOX` | `-97.45,49.70,-96.85,50.05` | Area kept: west, south, east, north |

## Production

Not set up yet: the live server doesn't run OSRM. That's a follow-up to #23 (planned: build images with the Winnipeg graphs inside, in the deploy pipeline, so the server needs no manual setup).
