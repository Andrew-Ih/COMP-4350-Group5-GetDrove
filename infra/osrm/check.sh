#!/usr/bin/env bash
# Checks that both OSRM instances answer with a sensible Winnipeg route (#23):
# Osborne Village to University Centre, by car and on foot.
#
#   bash infra/osrm/check.sh
set -euo pipefail

CAR_URL="${OSRM_CAR_URL:-http://localhost:5050}"
FOOT_URL="${OSRM_FOOT_URL:-http://localhost:5051}"
FROM="-97.1438,49.8768"  # Osborne Village (lng,lat, the order OSRM uses)
TO="-97.1366,49.8075"    # University Centre, Fort Garry campus

check() {
  local name="$1" url="$2" min_km="$3" max_km="$4"
  local body
  if ! body="$(curl -fsS "$url/route/v1/$name/$FROM;$TO?overview=false")"; then
    echo "FAIL  $name: no answer from $url (is it running? see infra/osrm/README.md)"
    return 1
  fi
  python3 - "$name" "$min_km" "$max_km" "$body" <<'PY'
import json, sys
name, low, high, body = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
data = json.loads(body)
if data.get("code") != "Ok":
    sys.exit(f"FAIL  {name}: OSRM said {data.get('code')}: {data.get('message', '')}")
route = data["routes"][0]
km, minutes = route["distance"] / 1000, route["duration"] / 60
status = "OK  " if low <= km <= high else "FAIL"
print(f"{status}  {name}: {km:.1f} km, {minutes:.0f} min")
sys.exit(0 if status == "OK  " else 1)
PY
}

# About 9-10 km by road; anything far outside that means the wrong area or a broken graph.
check driving "$CAR_URL" 7 14
check foot "$FOOT_URL" 7 14
