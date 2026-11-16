"""Writes the API contracts to contracts/:

- contracts/openapi/<service>.json: each service's OpenAPI spec
- contracts/events/<event>.v<N>.json: the JSON Schema of each shared event

Run after changing an API or event, and commit the result so reviewers see contract changes
in the PR and the frontend can generate types without running the services:

    uv run python scripts/export_openapi.py           # write the files
    uv run python scripts/export_openapi.py --check   # fail if any file is out of date (CI)

Files in contracts/openapi/ or contracts/events/ that the code no longer produces (an event
or service that was removed) count as out of date too: --check reports them and writing
deletes them (#178).
"""

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

from events.catalog import ALL_EVENTS

SERVICES = ["accounts", "trips", "routing", "payments", "notifications"]
CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


def _json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def openapi_files() -> dict[Path, str]:
    files = {}
    for service in SERVICES:
        module = importlib.import_module(f"{service}.infrastructure.main")
        spec = module.create_app().openapi()
        # Paths in the spec are relative to the gateway prefix.
        spec["servers"] = [{"url": f"/api/{service}"}]
        files[CONTRACTS / "openapi" / f"{service}.json"] = _json(spec)
    return files


def event_files() -> dict[Path, str]:
    files = {}
    for event in ALL_EVENTS:
        kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", event.event_type).lower()
        schema = event.model_json_schema(by_alias=True)
        schema["title"] = event.event_type
        schema["x-event-version"] = event.event_version
        files[CONTRACTS / "events" / f"{kebab}.v{event.event_version}.json"] = _json(schema)
    return files


def leftover_files(expected: dict[Path, str]) -> list[Path]:
    """Contract files the code doesn't produce any more."""
    existing = [*CONTRACTS.glob("openapi/*.json"), *CONTRACTS.glob("events/*.json")]
    return sorted(path for path in existing if path not in expected)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export API and event contracts.")
    parser.add_argument("--check", action="store_true", help="fail if any file is out of date")
    args = parser.parse_args()

    expected = {**openapi_files(), **event_files()}
    stale = []
    for path, content in expected.items():
        if path.exists() and path.read_text() == content:
            continue
        if args.check:
            stale.append(str(path.relative_to(CONTRACTS.parent)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(CONTRACTS.parent)}")

    for path in leftover_files(expected):
        if args.check:
            stale.append(f"{path.relative_to(CONTRACTS.parent)} (no longer produced)")
        else:
            path.unlink()
            print(f"removed {path.relative_to(CONTRACTS.parent)}")

    if stale:
        print(f"Out of date: {', '.join(stale)}. Run: uv run python scripts/export_openapi.py")
        return 1
    print("Contracts are up to date." if args.check else "Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
