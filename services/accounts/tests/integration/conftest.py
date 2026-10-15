"""A real PostgreSQL for the accounts integration tests.

One throwaway database per test run (testcontainers, so Docker must be running; GitHub
Actions runners have it). It's set up the way infra/postgres/init does it: an ``accounts``
user that owns an ``accounts`` schema. Then the real Alembic migrations run, so every test
also checks them. Without Docker these tests are skipped with a message.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from accounts.infrastructure.main import create_app

ACCOUNTS_DIR = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    try:
        import docker  # installed with testcontainers

        docker.from_env().ping()
    except Exception:
        return False
    return True


async def _create_accounts_user_and_schema(admin_url: str) -> None:
    """What infra/postgres/init/20-create-service-schemas.sh does for accounts."""
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("CREATE ROLE accounts LOGIN PASSWORD 'accounts'"))
        await conn.execute(text("CREATE SCHEMA accounts AUTHORIZATION accounts"))
        await conn.execute(text("ALTER ROLE accounts SET search_path = accounts, public"))
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """The accounts user's connection URL, with the migrations applied."""
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run integration tests")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        admin_url = postgres.get_connection_url()
        asyncio.run(_create_accounts_user_and_schema(admin_url))
        host = postgres.get_container_host_ip()
        port = postgres.get_exposed_port(5432)
        url = f"postgresql+asyncpg://accounts:accounts@{host}:{port}/{postgres.dbname}"

        # migrations/env.py reads the URL from the service's settings.
        previous = os.environ.get("ACCOUNTS_DATABASE_URL")
        os.environ["ACCOUNTS_DATABASE_URL"] = url
        try:
            command.upgrade(_alembic_config(), "head")
            yield url
        finally:
            if previous is None:
                os.environ.pop("ACCOUNTS_DATABASE_URL", None)
            else:
                os.environ["ACCOUNTS_DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """A throwaway Redis, for checking that events reach the stream."""
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run integration tests")
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7.4-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


def _alembic_config() -> Config:
    # No alembic.ini here on purpose: loading it reconfigures logging for the whole test run.
    config = Config()
    config.set_main_option("script_location", str(ACCOUNTS_DIR / "migrations"))
    return config


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    """Alembic, pointed at the test database."""
    return _alembic_config()


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    """A session on empty accounts tables."""
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        # CASCADE also empties the token tables; outbox has no link to users, so it's named.
        await conn.execute(text("TRUNCATE accounts.users, accounts.outbox CASCADE"))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def api(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """The real Accounts app on the test database, called over HTTP (no server needed).

    Its startup (the outbox relay) doesn't run here, so events stay in the outbox where
    tests can check them.
    """
    app = create_app()  # ACCOUNTS_DATABASE_URL points at the test database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await app.state.sessions.kw["bind"].dispose()
