"""Creates the FastAPI app for the payments service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from common_web.app import install
from payments.adapters.api import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove payments service",
        version="0.1.0",
    )
    install(app, service="payments")
    app.include_router(health.router)
    app.include_router(payments_router.internal_router)
    return app


app = create_app()
