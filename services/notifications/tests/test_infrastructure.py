"""Startup details from review on #218: a consumer that stops with an error is logged
instead of failing silently, and Redis reads outlast the consumer's wait."""

import asyncio
import logging

import pytest

from events import stream_name
from notifications.infrastructure.main import (
    CONSUMED_STREAMS,
    CONSUMER_BLOCK_MS,
    _log_if_consumer_stopped,
    redis_client,
)


async def test_a_consumer_that_crashes_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    async def crash() -> None:
        raise ConnectionError("Redis isn't reachable")

    task = asyncio.create_task(crash())
    await asyncio.gather(task, return_exceptions=True)

    with caplog.at_level(logging.ERROR):
        _log_if_consumer_stopped(task)

    [record] = caplog.records
    assert record.levelno == logging.ERROR
    assert "no emails will be sent" in record.getMessage()


async def test_a_normal_shutdown_isnt_logged(caplog: pytest.LogCaptureFixture) -> None:
    task = asyncio.create_task(asyncio.sleep(10))
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    with caplog.at_level(logging.ERROR):
        _log_if_consumer_stopped(task)

    assert caplog.records == []


def test_redis_reads_outlast_the_consumers_wait() -> None:
    client = redis_client("redis://localhost:6379/0")

    timeout = client.connection_pool.connection_kwargs["socket_timeout"]

    assert timeout > CONSUMER_BLOCK_MS / 1000


def test_reads_the_streams_notifications_come_from() -> None:
    """Accounts (verification emails, driver approval), Trips (requests and trips) and
    Payments (failed holds), #146."""
    assert set(CONSUMED_STREAMS) == {
        stream_name("accounts"),
        stream_name("trips"),
        stream_name("payments"),
    }
