"""Fixtures for the event library's tests.

Integration tests start a throwaway PostgreSQL and Redis with testcontainers, so they
need Docker running (locally: Docker Desktop; GitHub Actions runners have Docker).
If Docker isn't available, those tests are skipped with a message.
"""

from collections.abc import Iterator

import pytest


def _docker_available() -> bool:
    try:
        import docker  # installed with testcontainers

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run integration tests")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker isn't running; start Docker Desktop to run integration tests")
    from testcontainers.community.redis import RedisContainer

    with RedisContainer("redis:7.4-alpine") as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
