"""Creates the FastAPI app for the accounts service.

To run it locally, see the service README.
"""

from fastapi import FastAPI

from accounts.adapters.api import auth_router, health


def create_app() -> FastAPI:
    app = FastAPI(
        title="GetDrove accounts service",
        version="0.1.0",
    )
    app.include_router(health.router)
    app.include_router(auth_router.auth_router)
    app.include_router(auth_router.users_router)
    app.include_router(auth_router.keys_router)
    return app


app = create_app()
