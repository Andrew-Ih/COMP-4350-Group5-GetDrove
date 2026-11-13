"""Creates the FastAPI app for the payments service.

To run it locally, see the service README.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from stripe import HTTPXClient

from common_security.dependencies import install_security
from common_web.app import install
from payments.adapters.api import health, payments_router
from payments.adapters.api.payments_router import PricingConfig, get_pricing_config
from payments.infrastructure.gateway import create_payment_gateway
from payments.infrastructure.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
    stripe_http = HTTPXClient(timeout=10)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            # Stripe 14 exposes close_async without type annotations.
            await cast(Callable[[], Awaitable[None]], stripe_http.close_async)()
            await engine.dispose()

    app = FastAPI(
        title="GetDrove payments service",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
    app.state.payment_gateway = (
        create_payment_gateway(settings, stripe_http) if settings.stripe_secret_key else None
    )
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
