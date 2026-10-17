"""Creates the FastAPI app for the notifications service.

To run it locally, see the service README.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.dependencies import install_security
from common_web.app import install
from events import stream_name
from events.consumer import StreamConsumer
from notifications.adapters.api import health
from notifications.adapters.email.smtp_sender import SmtpEmailSender, SmtpSettings
from notifications.adapters.events.handlers import register_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.application.send_verification_email import SendVerificationEmail
from notifications.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)

# How long the consumer waits on Redis for new events before checking again.
CONSUMER_BLOCK_MS = 5_000
# Redis reads must outlast that wait. With no read timeout of its own, redis-py waits
# exactly as long as the block, and when nothing arrives the two race: it often gives up
# just before Redis answers "nothing new", logging a TimeoutError every few seconds.
REDIS_READ_TIMEOUT_SECONDS = 10


def redis_client(url: str) -> Redis:
    return Redis.from_url(url, socket_timeout=REDIS_READ_TIMEOUT_SECONDS)


def _log_if_consumer_stopped(task: "asyncio.Task[None]") -> None:
    """The consumer should run until shutdown. If it stops with an error (for example,
    Redis was unreachable while it set up its consumer group), say so loudly: otherwise
    the service looks healthy but never sends an email."""
    if not task.cancelled() and task.exception() is not None:
        logger.error("Event consumer stopped; no emails will be sent", exc_info=task.exception())


def create_app() -> FastAPI:
    settings = get_settings()

    # One connection pool for the whole service; it only connects when first used.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sender = SmtpEmailSender(
        SmtpSettings(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.email_from,
            username=settings.smtp_username,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
        )
    )
    send_email = SendVerificationEmail(sender, settings.web_base_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Reads Accounts' events for as long as the service runs.
        redis = redis_client(settings.redis_url)
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group="notifications",
            streams=[stream_name("accounts")],
            tables=consumer_tables,
            block_ms=CONSUMER_BLOCK_MS,
        )
        register_handlers(consumer, send_email)
        stop = asyncio.Event()
        consumer_task = asyncio.create_task(consumer.run(stop))
        consumer_task.add_done_callback(_log_if_consumer_stopped)
        try:
            yield
        finally:
            stop.set()
            # The consumer may be waiting up to 5 s for new events; don't hold shutdown up.
            consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer_task
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="GetDrove notifications service",
        version="0.1.0",
        lifespan=lifespan,
    )
    install(app, service="notifications")
    install_security(app)
    app.state.engine = engine
    app.state.sessions = sessions
    app.include_router(health.router)
    return app


app = create_app()
