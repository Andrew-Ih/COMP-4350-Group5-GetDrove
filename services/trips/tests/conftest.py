"""Shared test fixtures: Routing failures exercised at both the HTTP boundary and the Trips
API, and the throwaway test database."""

import asyncio
import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.fixture(
    params=[
        "invalid-json",
        "list",
        "null",
        "missing-id",
        "missing-distance",
        "missing-duration",
        "wrong-id",
        "id-type",
        "http-error",
        "timeout",
        *[
            f"{field}:{value}"
            for field in ("distanceMeters", "durationSeconds")
            for value in ("negative", "string", "float", "bool", "null", "object", "overflow")
        ],
    ]
)
def routing_failure(request: pytest.FixtureRequest) -> Callable[[httpx.Request], httpx.Response]:
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("Routing timed out", request=message)
        if case == "http-error":
            return httpx.Response(503)
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "list":
            return httpx.Response(200, json=[])
        if case == "null":
            return httpx.Response(200, content=b"null")
        data: dict[str, Any] = {
            "tripId": json.loads(message.content)["tripId"],
            "distanceMeters": 6000,
            "durationSeconds": 900,
        }
        missing = {
            "missing-id": "tripId",
            "missing-distance": "distanceMeters",
            "missing-duration": "durationSeconds",
        }
        if case in missing:
            del data[missing[case]]
        elif case == "wrong-id":
            data["tripId"] = "00000000-0000-0000-0000-000000000000"
        elif case == "id-type":
            data["tripId"] = 12
        else:
            field, value = case.split(":")
            data[field] = {
                "negative": -1,
                "string": "123",
                "float": 1.5,
                "bool": True,
                "null": None,
                "object": {},
                "overflow": 2**31,
            }[value]
        return httpx.Response(200, json=data)

    return handler


# ---------------------------------------------------------------- test database (#245)
#
# One throwaway PostgreSQL database per test run (testcontainers, so Docker must be
# running; GitHub Actions runners have it), set up the way infra/postgres/init does it: a
# `trips` user that owns a `trips` schema. The real Alembic migrations run on
# it, so the tests also check them. Tests that need it say so with
# `pytestmark = pytest.mark.usefixtures("trips_database")`; they read the URL through
# `get_settings()`, like the service. Without Docker they're skipped with a message.

TRIPS_DIR = Path(__file__).resolve().parents[1]


def _docker_available() -> bool:
    try:
        import docker  # installed with testcontainers

        docker.from_env().ping()
    except Exception:
        return False
    return True


async def _create_trips_user_and_schema(admin_url: str) -> None:
    """What infra/postgres/init/20-create-service-schemas.sh does for trips."""
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("CREATE ROLE trips LOGIN PASSWORD 'trips'"))
        await conn.execute(text("CREATE SCHEMA trips AUTHORIZATION trips"))
        await conn.execute(text("ALTER ROLE trips SET search_path = trips, public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def trips_database() -> Iterator[str]:
    """The trips user's connection URL on a fresh database, with the migrations applied."""
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run the database tests")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        asyncio.run(_create_trips_user_and_schema(postgres.get_connection_url()))
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        url = f"postgresql+asyncpg://trips:trips@{host}:{port}/{postgres.dbname}"

        # get_settings() (in the tests and in migrations/env.py) reads it from here.
        previous = os.environ.get("TRIPS_DATABASE_URL")
        os.environ["TRIPS_DATABASE_URL"] = url
        try:
            config = Config()  # no alembic.ini: loading it reconfigures logging for the run
            config.set_main_option("script_location", str(TRIPS_DIR / "migrations"))
            command.upgrade(config, "head")
            yield url
        finally:
            if previous is None:
                os.environ.pop("TRIPS_DATABASE_URL", None)
            else:
                os.environ["TRIPS_DATABASE_URL"] = previous
