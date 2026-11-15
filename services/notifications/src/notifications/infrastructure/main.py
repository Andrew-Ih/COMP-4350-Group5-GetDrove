"""Creates the FastAPI app for the notifications service.

To run it locally, see the service README.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from common_security.dependencies import install_security
from common_web.app import install
from events import stream_name
from events.consumer import StreamConsumer
from notifications.adapters.accounts import HTTPContactDirectory
from notifications.adapters.api import health, notifications_router
from notifications.adapters.email.smtp_sender import SmtpEmailSender, SmtpSettings
from notifications.adapters.events.handlers import register_handlers
from notifications.adapters.events.notification_handlers import notification_handlers
from notifications.adapters.events.registration import register_event_handlers
from notifications.adapters.events.reminder_handlers import reminder_handlers
from notifications.adapters.persistence.tables import consumer as consumer_tables
from notifications.adapters.reminder_scheduler import ReminderScheduler
from notifications.application.send_verification_email import SendVerificationEmail
from notifications.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)

# Accounts' events ask for verification emails (#93) and tell drivers about approval;
# Trips' and Payments' events become notifications (#146).
CONSUMED_STREAMS = [stream_name("accounts"), stream_name("trips"), stream_name("payments")]
# How long to wait for Accounts when looking up where to send emails.
ACCOUNTS_TIMEOUT_SECONDS = 5.0

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


def _log_if_scheduler_stopped(task: "asyncio.Task[None]") -> None:
    """Like the consumer: if the reminder scheduler stops with an error, say so loudly."""
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "Reminder scheduler stopped; no reminders will be sent", exc_info=task.exception()
        )


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
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            starttls=settings.smtp_starttls,
        )
    )
    send_email = SendVerificationEmail(sender, settings.web_base_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Reads events for as long as the service runs.
        redis = redis_client(settings.redis_url)
        accounts = httpx.AsyncClient(
            base_url=settings.accounts_url, timeout=ACCOUNTS_TIMEOUT_SECONDS
        )
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group="notifications",
            streams=CONSUMED_STREAMS,
            tables=consumer_tables,
            block_ms=CONSUMER_BLOCK_MS,
        )
        register_handlers(consumer, send_email)
        register_event_handlers(
            consumer,
            notification_handlers(
                contacts=HTTPContactDirectory(accounts),
                sender=sender,
                web_base_url=settings.web_base_url,
            ),
            reminder_handlers(timedelta(minutes=settings.reminder_lead_minutes)),
        )
        # Sends reminders when they're due (#149), including ones missed while it was down.
        scheduler = ReminderScheduler(
            sessions=sessions,
            contacts=HTTPContactDirectory(accounts),
            sender=sender,
            web_base_url=settings.web_base_url,
        )
        stop = asyncio.Event()
        consumer_task = asyncio.create_task(consumer.run(stop))
        consumer_task.add_done_callback(_log_if_consumer_stopped)
        scheduler_task = asyncio.create_task(
            scheduler.run(stop, interval_seconds=settings.reminder_interval_seconds)
        )
        scheduler_task.add_done_callback(_log_if_scheduler_stopped)
        try:
            yield
        finally:
            stop.set()
            # The consumer may be waiting up to 5 s for new events, and the scheduler up to
            # 30 s for its next pass; don't hold shutdown up.
            for task in (consumer_task, scheduler_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await accounts.aclose()
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
    app.include_router(notifications_router.router)
    return app


app = create_app()
