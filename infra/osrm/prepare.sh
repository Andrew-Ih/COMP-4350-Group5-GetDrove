#!/usr/bin/env bash
# Prepares the Winnipeg map data for OSRM, the routing engine (#23, ADR 0008).
#
#   bash infra/osrm/prepare.sh
#
# 1. Downloads the Manitoba OpenStreetMap extract from Geofabrik (about 200 MB, once).
# 2. Clips it to Winnipeg and the area around the Perimeter Highway.
# 3. Builds two routing graphs: car (driving routes) and foot (walking to pickup points).
#
# Everything runs in throwaway Docker containers, so nothing needs installing besides
# Docker and curl. The result goes to infra/osrm/data/ (gitignored, never committed).
# Run it again to pick up newer map data; it replaces the old graphs.
set -euo pipefail

cd "$(dirname "$0")"
DATA="$PWD/data"
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v5.27.1}"
EXTRACT_URL="${EXTRACT_URL:-https://download.geofabrik.de/north-america/canada/manitoba-latest.osm.pbf}"
# west,south,east,north: Winnipeg plus a margin past the Perimeter Highway (Hwy 100/101).
BBOX="${BBOX:--97.45,49.70,-96.85,50.05}"

mkdir -p "$DATA/car" "$DATA/foot"

if [ ! -f "$DATA/manitoba-latest.osm.pbf" ]; then
  echo "== Downloading the Manitoba extract"
  curl -fL --retry 3 -o "$DATA/manitoba-latest.osm.pbf.part" "$EXTRACT_URL"
  mv "$DATA/manitoba-latest.osm.pbf.part" "$DATA/manitoba-latest.osm.pbf"
else
  echo "== Using the Manitoba extract already downloaded (delete it to download a newer one)"
fi

echo "== Clipping to Winnipeg ($BBOX)"
docker run --rm -v "$DATA:/data" debian:bookworm-slim sh -c "
  apt-get update -qq >/dev/null && apt-get install -y -qq osmium-tool >/dev/null &&
  osmium extract --overwrite --bbox '$BBOX' -o /data/winnipeg.osm.pbf /data/manitoba-latest.osm.pbf"

for profile in car foot; do
  echo "== Building the $profile graph"
  rm -f "$DATA/$profile"/winnipeg.osrm*
  cp "$DATA/winnipeg.osm.pbf" "$DATA/$profile/winnipeg.osm.pbf"
  docker run --rm -v "$DATA/$profile:/data" "$OSRM_IMAGE" osrm-extract -p "/opt/$profile.lua" /data/winnipeg.osm.pbf
  # MLD: fast to build, and what osrm-routed is started with in docker-compose.yml.
  docker run --rm -v "$DATA/$profile:/data" "$OSRM_IMAGE" osrm-partition /data/winnipeg.osrm
  docker run --rm -v "$DATA/$profile:/data" "$OSRM_IMAGE" osrm-customize /data/winnipeg.osrm
  rm "$DATA/$profile/winnipeg.osm.pbf"
done

echo
echo "Done. Start OSRM with:  docker compose --profile osrm up -d osrm-car osrm-foot"
echo "Then check it with:     bash infra/osrm/check.sh"
