"""Creates the FastAPI app for the notifications service.

To run it locally, see the service README.
"""

import asyncio
import contextlib
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
        # Reads Accounts' events for as long as the service runs.
        redis = Redis.from_url(settings.redis_url)
        consumer = StreamConsumer(
            redis=redis,
            session_factory=sessions,
            group="notifications",
            streams=[stream_name("accounts")],
            tables=consumer_tables,
        )
        register_handlers(consumer, send_email)
        stop = asyncio.Event()
        consumer_task = asyncio.create_task(consumer.run(stop))
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
