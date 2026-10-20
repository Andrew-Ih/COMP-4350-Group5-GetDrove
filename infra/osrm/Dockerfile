# OSRM with the Winnipeg map built in (#23, #233, ADR 0008).
#
# One image per profile, built the same way locally (docker compose) and for the live
# server (deploy.yml), so the server never prepares map data itself:
#
#   docker build --build-arg PROFILE=car  -t getdrove-osrm-car  infra/osrm
#   docker build --build-arg PROFILE=foot -t getdrove-osrm-foot infra/osrm
#
# The map download and clip are cached: they only run again when OSRM_VERSION, BBOX,
# EXTRACT_URL or MAP_REFRESH change. See infra/osrm/README.md.

ARG OSRM_VERSION=v5.27.1

# ---------------------------------------------------------------- 1. map: Winnipeg only
FROM debian:bookworm-slim AS map

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl osmium-tool \
 && rm -rf /var/lib/apt/lists/*

ARG EXTRACT_URL=https://download.geofabrik.de/north-america/canada/manitoba-latest.osm.pbf
# west,south,east,north: Winnipeg plus a margin past the Perimeter Highway (Hwy 100/101).
ARG BBOX=-97.45,49.70,-96.85,50.05
# Change it (deploy.yml's "refresh_map" does) to download the latest map instead of the
# cached one.
ARG MAP_REFRESH=cached

WORKDIR /map
RUN echo "map: $MAP_REFRESH" \
 && curl -fsSL --retry 3 -o manitoba.osm.pbf "$EXTRACT_URL" \
 && osmium extract --bbox "$BBOX" -o winnipeg.osm.pbf manitoba.osm.pbf \
 && rm manitoba.osm.pbf

# ---------------------------------------------------------------- 2. graph for one profile
FROM ghcr.io/project-osrm/osrm-backend:${OSRM_VERSION} AS graph

# car (driving routes, road names) or foot (walking times).
ARG PROFILE
RUN test "$PROFILE" = car || test "$PROFILE" = foot \
 || { echo "Build with --build-arg PROFILE=car or PROFILE=foot" >&2; exit 1; }

WORKDIR /data
COPY --from=map /map/winnipeg.osm.pbf .
# MLD: quick to build, and what osrm-routed runs with below.
RUN osrm-extract -p "/opt/$PROFILE.lua" winnipeg.osm.pbf \
 && osrm-partition winnipeg.osrm \
 && osrm-customize winnipeg.osrm \
 && rm winnipeg.osm.pbf

# ---------------------------------------------------------------- 3. the server
FROM ghcr.io/project-osrm/osrm-backend:${OSRM_VERSION}

COPY --from=graph /data /data

EXPOSE 5000

# The image has no curl; bash can still check that the port answers.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["bash", "-c", ":> /dev/tcp/127.0.0.1/5000"]

# --verbosity WARNING: at OSRM's default (INFO), osrm-routed logs every request's URL, and
# the URL holds riders' and drivers' coordinates, which must never be stored.
CMD ["osrm-routed", "--algorithm", "mld", "--verbosity", "WARNING", "/data/winnipeg.osrm"]
