"""A real PostgreSQL (and Redis) for the notifications integration tests.

One throwaway database per test run (testcontainers, so Docker must be running; GitHub
Actions runners have it), set up the way infra/postgres/init does it: a ``notifications``
user that owns a ``notifications`` schema. Then the real Alembic migrations run, so every
test also checks them. Without Docker these tests are skipped with a message.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOTIFICATIONS_DIR = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    try:
        import docker  # installed with testcontainers

        docker.from_env().ping()
    except Exception:
        return False
    return True


async def _create_user_and_schema(admin_url: str) -> None:
    """What infra/postgres/init/20-create-service-schemas.sh does for notifications."""
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("CREATE ROLE notifications LOGIN PASSWORD 'notifications'"))
        await conn.execute(text("CREATE SCHEMA notifications AUTHORIZATION notifications"))
        await conn.execute(text("ALTER ROLE notifications SET search_path = notifications, public"))
    await engine.dispose()


def _alembic_config() -> Config:
    # No alembic.ini here on purpose: loading it reconfigures logging for the whole test run.
    config = Config()
    config.set_main_option("script_location", str(NOTIFICATIONS_DIR / "migrations"))
    return config


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """The notifications user's connection URL, with the migrations applied."""
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run integration tests")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        asyncio.run(_create_user_and_schema(postgres.get_connection_url()))
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        url = f"postgresql+asyncpg://notifications:notifications@{host}:{port}/{postgres.dbname}"

        # migrations/env.py reads the URL from the service's settings.
        previous = os.environ.get("NOTIFICATIONS_DATABASE_URL")
        os.environ["NOTIFICATIONS_DATABASE_URL"] = url
        try:
            command.upgrade(_alembic_config(), "head")
            yield url
        finally:
            if previous is None:
                os.environ.pop("NOTIFICATIONS_DATABASE_URL", None)
            else:
                os.environ["NOTIFICATIONS_DATABASE_URL"] = previous


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    """Alembic, pointed at the test database."""
    return _alembic_config()


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    """A session on empty notifications tables."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE notifications.processed_events, notifications.failed_events")
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()
