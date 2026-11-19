"""Creates the FastAPI app for the routing service.

To run it locally, see the service README.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from common_security.dependencies import install_security
from common_web.app import install
from events import stream_name
from events.consumer import StreamConsumer
from routing.adapters.api import health, routing_router
from routing.adapters.events.handlers import register_handlers
from routing.adapters.nominatim import NominatimPlaceFinder, PoliteFinder, Throttle
from routing.adapters.persistence.tables import consumer as consumer_tables
from routing.adapters.redis_plans import RedisDetourPlans
from routing.domain.values import Corridor
from routing.infrastructure.database import create_database_engine
from routing.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)

# How long the consumer waits on Redis for new events before checking again, and how long
# its Redis reads may take: longer, or the two race (see libs/events/README.md).
CONSUMER_BLOCK_MS = 5_000
CONSUMER_READ_TIMEOUT_SECONDS = 10


def _log_if_consumer_stopped(task: "asyncio.Task[None]") -> None:
    """Quotes still work without the consumer (plans are keyed by their points), but say so
    loudly if it stops with an error."""
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "Event consumer stopped; detour plans won't be freed early", exc_info=task.exception()
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close infrastructure resources."""

    settings = get_settings()

    engine = create_database_engine(settings.database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.corridor = Corridor(radius_meters=settings.corridor_meters)
    app.state.max_walk_seconds = settings.max_walk_seconds
    app.state.detour_timeout_seconds = settings.detour_timeout_seconds

    # Two connections: the cache must answer fast or be skipped, while the consumer's reads
    # wait for new events.
    cache_redis = Redis.from_url(
        settings.redis_url,
        socket_timeout=settings.plan_cache_timeout_seconds,
        socket_connect_timeout=settings.plan_cache_timeout_seconds,
    )
    events_redis = Redis.from_url(settings.redis_url, socket_timeout=CONSUMER_READ_TIMEOUT_SECONDS)
    plans = RedisDetourPlans(cache_redis, ttl_seconds=settings.detour_plan_ttl_seconds)
    app.state.detour_plans = plans

    consumer = StreamConsumer(
        redis=events_redis,
        session_factory=app.state.session_factory,
        group="routing",
        streams=[stream_name("trips")],
        tables=consumer_tables,
        block_ms=CONSUMER_BLOCK_MS,
    )
    register_handlers(consumer, plans)

    async with (
        httpx.AsyncClient(
            base_url=settings.osrm_car_url, timeout=settings.osrm_timeout_seconds
        ) as osrm_car_client,
        httpx.AsyncClient(
            base_url=settings.osrm_foot_url, timeout=settings.osrm_timeout_seconds
        ) as osrm_foot_client,
        httpx.AsyncClient(
            base_url=settings.geocoder_url,
            timeout=settings.geocoder_timeout_seconds,
            headers={"User-Agent": settings.geocoder_user_agent},
        ) as geocoder_client,
    ):
        app.state.osrm_car_client = osrm_car_client
        app.state.osrm_foot_client = osrm_foot_client
        app.state.place_finder = PoliteFinder(
            NominatimPlaceFinder(geocoder_client),
            Throttle(
                min_interval=settings.geocoder_min_interval_seconds,
                max_wait=settings.geocoder_max_wait_seconds,
            ),
            ttl_seconds=settings.places_cache_ttl_seconds,
            max_entries=settings.places_cache_max_entries,
        )
        stop = asyncio.Event()
        consumer_task = asyncio.create_task(consumer.run(stop))
        consumer_task.add_done_callback(_log_if_consumer_stopped)
        try:
            yield
        finally:
            stop.set()
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer_task
            await cache_redis.aclose()
            await events_redis.aclose()
            await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove routing service",
        version="0.1.0",
        lifespan=lifespan,
    )
    install(app, service="routing")
    install_security(app)
    app.include_router(health.router)
    app.include_router(routing_router.internal_router)
    app.include_router(routing_router.public_router)
    app.include_router(routing_router.places_router)
    return app


app = create_app()
