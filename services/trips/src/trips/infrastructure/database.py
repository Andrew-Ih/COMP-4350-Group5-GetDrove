"""The database engine for the service (#31)."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(url: str) -> AsyncEngine:
    """The engine the service uses. ``hide_parameters``: SQLAlchemy puts a failed query's
    parameters in the error message, and an unexpected error is logged with its traceback.
    Saving a trip sends the driver's own place (near home), so without this a database
    outage while posting would write it to the logs. The database driver's own error text
    can still quote a value, so the logs also take coordinates out (``common_web.logs``)."""
    return create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
