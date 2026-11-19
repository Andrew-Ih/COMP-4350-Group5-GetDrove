"""Workspace-level fixtures for contract integration across services."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SERVICES = ("payments", "trips", "notifications")
ROOT = Path(__file__).resolve().parents[2]


async def create_schemas(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            for service in SERVICES:
                await conn.execute(text(f'CREATE SCHEMA "{service}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def failure_database() -> Iterator[str]:
    import docker
    from testcontainers.community.postgres import PostgresContainer

    try:
        docker.from_env().ping()
    except docker.errors.DockerException:
        pytest.skip("Docker is required for cross-service payment failure tests")
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url() + "?ssl=disable"
        asyncio.run(create_schemas(url))
        with pytest.MonkeyPatch.context() as patch:
            for service in SERVICES:
                patch.setenv(f"{service.upper()}_DATABASE_URL", url)
                config = Config()
                config.set_main_option(
                    "script_location", str(ROOT / "services" / service / "migrations")
                )
                command.upgrade(config, "head")
        yield url


@pytest.fixture(scope="session")
def failure_redis(failure_database: str) -> Iterator[str]:
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7.4-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
