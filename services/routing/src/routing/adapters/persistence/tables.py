"""SQLAlchemy table definitions for the routing schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Table,
    Uuid,
    func,
)

SCHEMA = "routing"

# WGS 84 longitude/latitude, the coordinates OSRM and the frontend use.
SRID = 4326

metadata = MetaData(
    schema=SCHEMA,
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)

# One driving route per trip (#24). Matching (#25, #26) searches these by location.
routes = Table(
    "routes",
    metadata,
    Column("trip_id", Uuid, primary_key=True),
    # The spatial index is declared below, so Alembic sees it like any other index.
    Column("path", Geometry("LINESTRING", srid=SRID, spatial_index=False), nullable=False),
    Column("distance_meters", Integer, nullable=False),
    Column("duration_seconds", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "distance_meters >= 0 AND duration_seconds >= 0",
        name="valid_route_metrics",
    ),
    Index("ix_routes_path", "path", postgresql_using="gist"),
)
