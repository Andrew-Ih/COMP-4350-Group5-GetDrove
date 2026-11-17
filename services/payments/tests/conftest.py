"""Isolated infrastructure for hold tests; never migrate the developer's database."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def prepare(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA payments"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def payments_database() -> Iterator[str]:
    import docker
    from testcontainers.community.postgres import PostgresContainer

    try:
        docker.from_env().ping()
    except docker.errors.DockerException:
        pytest.skip("Docker is not running; start Docker Desktop for hold integration tests")
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        # This disposable Postgres has no TLS. Avoid SSL negotiation through Docker's
        # Windows port proxy; production connection settings are not changed.
        url = postgres.get_connection_url() + "?ssl=disable"
        asyncio.run(prepare(url))
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("PAYMENTS_DATABASE_URL", url)
            config = Config()
            config.set_main_option(
                "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
            )
            command.upgrade(config, "head")
        yield url


@pytest.fixture(scope="session")
def payments_redis(payments_database: str) -> Iterator[str]:
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7.4-alpine") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
