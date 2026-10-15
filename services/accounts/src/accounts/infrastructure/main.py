"""Creates the FastAPI app for the accounts service.

To run it locally, see the service README.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from accounts.adapters.api import auth_router, health
from accounts.adapters.persistence.tables import outbox
from accounts.adapters.security.signing_key import load_signing_key
from accounts.infrastructure.settings import get_settings
from common_security.dependencies import install_security
from common_security.keys import StaticKeys
from common_web.app import install
from events.outbox import OutboxRelay


def create_app() -> FastAPI:
    settings = get_settings()

    # One connection pool for the whole service; it only connects when first used.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Sends saved events (outbox) to Redis for as long as the service runs.
        redis = Redis.from_url(settings.redis_url)
        relay = OutboxRelay(
            session_factory=sessions, redis=redis, table=outbox, producer="accounts"
        )
        stop = asyncio.Event()
        relay_task = asyncio.create_task(relay.run(stop))
        try:
            yield
        finally:
            stop.set()
            await relay_task
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="GetDrove accounts service",
        version="0.1.0",
        lifespan=lifespan,
    )
    install(app, service="accounts")
    app.state.sessions = sessions

    # Accounts signs tokens and checks its own tokens with the same key (no JWKS fetch).
    signing_key = load_signing_key(settings.jwt_private_key, environment=settings.environment)
    app.state.signing_key = signing_key
    install_security(app, keys=StaticKeys(signing_key.jwks()))

    app.include_router(health.router)
    app.include_router(auth_router.auth_router)
    app.include_router(auth_router.users_router)
    app.include_router(auth_router.keys_router)
    return app


app = create_app()
