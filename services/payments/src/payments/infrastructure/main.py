"""Creates the FastAPI app for the payments service.

To run it locally, see the service README.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from stripe import HTTPXClient

from common_security.dependencies import install_security
from common_web.app import install
from events import stream_name
from events.consumer import StreamConsumer
from events.outbox import OutboxRelay
from payments.adapters.api import health, payments_router
from payments.adapters.api.payments_router import PricingConfig, get_pricing_config
from payments.adapters.configured_cards import ConfiguredSavedCardLookup
from payments.adapters.hold_events import register_hold_handlers
from payments.adapters.persistence.tables import consumer as consumer_tables
from payments.adapters.persistence.tables import outbox
from payments.application.ports import SavedCardLookup
from payments.infrastructure.gateway import create_payment_gateway
from payments.infrastructure.hold_worker import HoldWorker
from payments.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)


def create_app(saved_cards: SavedCardLookup | None = None) -> FastAPI:
    settings = get_settings()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    stripe_http = HTTPXClient(timeout=10)
    gateway = create_payment_gateway(settings, stripe_http) if settings.stripe_secret_key else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        redis = None
        stop = asyncio.Event()
        tasks: list[asyncio.Task[None]] = []
        try:
            if settings.hold_processing_enabled:
                lookup = saved_cards
                if lookup is None and settings.saved_card_references:
                    lookup = ConfiguredSavedCardLookup(settings.saved_card_references)
                if lookup is None or gateway is None:
                    raise RuntimeError(
                        "Hold processing requires a saved-card lookup and Stripe test key"
                    )
                redis = Redis.from_url(settings.redis_url, socket_timeout=10)
                worker = HoldWorker(sessions, lookup, gateway)
                consumer = StreamConsumer(
                    redis=redis,
                    session_factory=sessions,
                    group="payments",
                    streams=[stream_name("trips")],
                    tables=consumer_tables,
                )
                register_hold_handlers(consumer)
                relay = OutboxRelay(
                    session_factory=sessions, redis=redis, table=outbox, producer="payments"
                )
                tasks = [
                    asyncio.create_task(consumer.run(stop)),
                    asyncio.create_task(relay.run(stop)),
                    asyncio.create_task(worker.run(stop)),
                ]

                def report_stopped(task: asyncio.Task[None]) -> None:
                    if not task.cancelled() and task.exception() is not None:
                        logger.error("Payment background task stopped", exc_info=task.exception())

                for task in tasks:
                    task.add_done_callback(report_stopped)
                app.state.hold_worker = worker
            yield
        finally:
            stop.set()
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            # Card endpoints and the worker share the bounded Stripe client and DB pool.
            await cast(Callable[[], Awaitable[None]], stripe_http.close_async)()
            if redis is not None:
                await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="GetDrove payments service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.sessions = sessions
    app.state.payment_gateway = gateway
    install(app, service="payments")
    install_security(app)
    app.include_router(health.router)
    app.include_router(payments_router.internal_router)
    app.include_router(payments_router.cards_router)

    def provide_pricing_config() -> PricingConfig:
        settings = get_settings()
        return PricingConfig(
            rate_cents_per_km=settings.rate_cents_per_km,
            minimum_fare_cents=settings.minimum_fare_cents,
        )

    app.dependency_overrides[get_pricing_config] = provide_pricing_config
    return app


app = create_app()
