"""Shared test fixtures: fake OSRM responses for the adapter and API tests, and the
throwaway test database."""

import asyncio
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

type Handler = Callable[[httpx.Request], httpx.Response]

# A short drive from Pembina Highway to campus, as OSRM returns it ([lng, lat] pairs).
OSRM_PATH = [[-97.15, 49.82], [-97.14, 49.815], [-97.1366, 49.8075]]


def osrm_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 6000.4,
                    "duration": 899.6,
                    "geometry": {"type": "LineString", "coordinates": OSRM_PATH},
                }
            ],
        },
    )


@pytest.fixture
def osrm_route() -> Handler:
    """OSRM finds a route. Its fractional meters and seconds round to 6000 and 900."""
    return osrm_ok


@pytest.fixture(
    params=[
        "timeout",
        "connect-error",
        "http-500",
        "invalid-json",
        "html",
        "error-code",
        "no-routes",
        "ok-with-400",
        "missing-geometry",
        "one-point",
        "negative-distance",
        "overflow-duration",
    ]
)
def osrm_failure(request: pytest.FixtureRequest) -> Handler:
    """Every way OSRM can fail that means "try again later" (503), not "bad input" (422)."""
    case = request.param

    def handler(message: httpx.Request) -> httpx.Response:
        if case == "timeout":
            raise httpx.ReadTimeout("OSRM timed out", request=message)
        if case == "connect-error":
            raise httpx.ConnectError("OSRM is not running", request=message)
        if case == "http-500":
            return httpx.Response(500, json={"code": "Error", "message": "boom"})
        if case == "invalid-json":
            return httpx.Response(200, content=b"not JSON")
        if case == "html":
            return httpx.Response(502, content=b"<html>Bad gateway</html>")
        if case == "error-code":
            return httpx.Response(400, json={"code": "InvalidQuery", "message": "bad"})
        if case == "no-routes":
            return httpx.Response(200, json={"code": "Ok", "routes": []})
        if case == "ok-with-400":
            return httpx.Response(400, json=osrm_ok(message).json())

        route: dict[str, Any] = osrm_ok(message).json()["routes"][0]
        if case == "missing-geometry":
            del route["geometry"]
        elif case == "one-point":
            route["geometry"]["coordinates"] = OSRM_PATH[:1]
        elif case == "negative-distance":
            route["distance"] = -1
        elif case == "overflow-duration":
            route["duration"] = 2**31
        return httpx.Response(200, json={"code": "Ok", "routes": [route]})

    return handler


@pytest.fixture(params=["NoRoute", "NoSegment"])
def osrm_no_route(request: pytest.FixtureRequest) -> Handler:
    """OSRM can't drive between the points: the caller's input is the problem (422)."""

    def handler(message: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": request.param, "message": "Impossible route"})

    return handler


# ---------------------------------------------------------------- test database (#245)
#
# One throwaway PostgreSQL + PostGIS database per test run (testcontainers, so Docker must be
# running; GitHub Actions runners have it), set up the way infra/postgres/init does it: a
# `routing` user that owns a `routing` schema, with PostGIS in the public schema. The real
# Alembic migrations run on it, so the tests also check them. Tests that need it say so with
# `pytestmark = pytest.mark.usefixtures("routing_database")`; they read the URL through
# `get_settings()`, like the service. Without Docker they're skipped with a message.

ROUTING_DIR = Path(__file__).resolve().parents[1]


def _docker_available() -> bool:
    try:
        import docker  # installed with testcontainers

        docker.from_env().ping()
    except Exception:
        return False
    return True


async def _create_routing_user_and_schema(admin_url: str) -> None:
    """What infra/postgres/init/20-create-service-schemas.sh does for routing."""
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.execute(text("CREATE ROLE routing LOGIN PASSWORD 'routing'"))
        await conn.execute(text("CREATE SCHEMA routing AUTHORIZATION routing"))
        await conn.execute(text("ALTER ROLE routing SET search_path = routing, public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def routing_database() -> Iterator[str]:
    """The routing user's connection URL on a fresh database, with the migrations applied."""
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run the database tests")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgis/postgis:17-3.5", driver="asyncpg") as postgres:
        asyncio.run(_create_routing_user_and_schema(postgres.get_connection_url()))
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        url = f"postgresql+asyncpg://routing:routing@{host}:{port}/{postgres.dbname}"

        # get_settings() (in the tests and in migrations/env.py) reads it from here.
        previous = os.environ.get("ROUTING_DATABASE_URL")
        os.environ["ROUTING_DATABASE_URL"] = url
        try:
            config = Config()  # no alembic.ini: loading it reconfigures logging for the run
            config.set_main_option("script_location", str(ROUTING_DIR / "migrations"))
            command.upgrade(config, "head")
            yield url
        finally:
            if previous is None:
                os.environ.pop("ROUTING_DATABASE_URL", None)
            else:
                os.environ["ROUTING_DATABASE_URL"] = previous
