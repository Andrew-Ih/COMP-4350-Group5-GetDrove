"""Creates the FastAPI app for the notifications service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from common_web.app import install
from notifications.adapters.api import health


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove notifications service",
        version="0.1.0",
    )
    install(app, service="notifications")
    app.include_router(health.router)
    return app


app = create_app()
