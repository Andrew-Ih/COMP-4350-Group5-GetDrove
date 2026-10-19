"""Creates the FastAPI app for the payments service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from common_security.dependencies import install_security
from common_web.app import install
from payments.adapters.api import health, payments_router
from payments.adapters.api.payments_router import PricingConfig, get_pricing_config
from payments.infrastructure.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove payments service",
        version="0.1.0",
    )
    install(app, service="payments")
    install_security(app)
    app.include_router(health.router)
    app.include_router(payments_router.internal_router)

    def provide_pricing_config() -> PricingConfig:
        settings = get_settings()
        return PricingConfig(
            rate_cents_per_km=settings.rate_cents_per_km,
            minimum_fare_cents=settings.minimum_fare_cents,
        )

    app.dependency_overrides[get_pricing_config] = provide_pricing_config
    return app


app = create_app()
