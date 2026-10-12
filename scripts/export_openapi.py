"""Writes each service's OpenAPI spec to contracts/openapi/<service>.json.

Run after changing an API, and commit the result so reviewers see contract changes in the
PR and the frontend can generate types without running the services:

    uv run python scripts/export_openapi.py           # write the files
    uv run python scripts/export_openapi.py --check   # fail if any file is out of date (CI)
"""

import argparse
import importlib
import json
import sys
from pathlib import Path

SERVICES = ["accounts", "trips", "routing", "payments", "notifications"]
OUT_DIR = Path(__file__).resolve().parent.parent / "contracts" / "openapi"


def spec_for(service: str) -> str:
    module = importlib.import_module(f"{service}.infrastructure.main")
    spec = module.create_app().openapi()
    # Paths in the spec are relative to the gateway prefix.
    spec["servers"] = [{"url": f"/api/{service}"}]
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if any file is out of date")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stale = []
    for service in SERVICES:
        path = OUT_DIR / f"{service}.json"
        spec = spec_for(service)
        current = path.read_text() if path.exists() else None
        if current == spec:
            continue
        if args.check:
            stale.append(path.name)
        else:
            path.write_text(spec)
            print(f"wrote {path.relative_to(OUT_DIR.parent.parent)}")

    if stale:
        print(f"Out of date: {', '.join(stale)}. Run: uv run python scripts/export_openapi.py")
        return 1
    print("Contracts are up to date." if args.check else "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
