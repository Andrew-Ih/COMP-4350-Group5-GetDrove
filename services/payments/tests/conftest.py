"""Throwaway database with the real Payments migrations, never a developer database."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def prepare(url: str) -> None:
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE SCHEMA payments"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def payments_database() -> Iterator[str]:
    import docker
    from testcontainers.community.postgres import PostgresContainer

    try:
        docker.from_env().ping()
    except docker.errors.DockerException:
        pytest.skip("Docker is not running; start Docker Desktop for Payments database tests")
    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        asyncio.run(prepare(url))
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("PAYMENTS_DATABASE_URL", url)
            config = Config()
            config.set_main_option(
                "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
            )
            command.upgrade(config, "head")
        yield url
