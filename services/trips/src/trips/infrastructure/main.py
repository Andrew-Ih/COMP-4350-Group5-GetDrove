"""Creates the FastAPI app for the trips service."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
)

from common_security.dependencies import install_security
from common_web.app import install
from events import stream_name
from events.consumer import StreamConsumer
from events.outbox import OutboxRelay
from trips.adapters.account_events import register_handlers
from trips.adapters.api import health, trips_router
from trips.adapters.persistence.tables import consumer as consumer_tables
from trips.adapters.persistence.tables import outbox
from trips.infrastructure.database import create_database_engine
from trips.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)

# How long the event consumer waits on Redis for new events before checking again. Reads
# must outlast it, or redis-py times out while idle (see the libs/events README).
CONSUMER_BLOCK_MS = 5_000
REDIS_READ_TIMEOUT_SECONDS = 10


def _log_if_consumer_stopped(task: "asyncio.Task[None]") -> None:
    """The consumer should run until shutdown. If it stops with an error, say so loudly:
    otherwise newly approved drivers would never be able to post."""
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "Event consumer stopped; driver approvals won't reach Trips",
            exc_info=task.exception(),
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close infrastructure resources."""

    settings = get_settings()

    engine = create_database_engine(settings.database_url)

    app.state.session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    redis = Redis.from_url(settings.redis_url, socket_timeout=REDIS_READ_TIMEOUT_SECONDS)
    relay = OutboxRelay(
        session_factory=app.state.session_factory, redis=redis, table=outbox, producer="trips"
    )
    # Accounts' driver decisions keep Trips' list of approved drivers up to date (#11).
    consumer = StreamConsumer(
        redis=redis,
        session_factory=app.state.session_factory,
        group="trips",
        streams=[stream_name("accounts")],
        tables=consumer_tables,
        block_ms=CONSUMER_BLOCK_MS,
    )
    register_handlers(consumer)

    async with (
        httpx.AsyncClient(
            base_url=settings.routing_url,
            timeout=5.0,
        ) as routing_client,
        # A price is optional in search results, so don't wait long for one.
        httpx.AsyncClient(
            base_url=settings.payments_url,
            timeout=2.0,
        ) as payments_client,
        httpx.AsyncClient(
            base_url=settings.accounts_url,
            timeout=2.0,
        ) as accounts_client,
    ):
        app.state.routing_client = routing_client
        app.state.payments_client = payments_client
        app.state.accounts_client = accounts_client
        stop = asyncio.Event()
        relay_task = asyncio.create_task(relay.run(stop))
        consumer_task = asyncio.create_task(consumer.run(stop))
        consumer_task.add_done_callback(_log_if_consumer_stopped)

        try:
            yield
        finally:
            stop.set()
            # The consumer may be waiting up to 5 s for new events; don't hold shutdown up.
            consumer_task.cancel()
            try:
                with contextlib.suppress(asyncio.CancelledError):
                    await consumer_task
                await relay_task
            finally:
                await redis.aclose()
                await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove trips service",
        version="0.1.0",
        lifespan=lifespan,
    )

    install(app, service="trips")
    install_security(app)

    app.include_router(health.router)
    app.include_router(trips_router.router)

    return app


app = create_app()
