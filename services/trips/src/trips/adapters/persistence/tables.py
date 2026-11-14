"""SQLAlchemy table definitions for the trips schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    func,
)

from events.outbox import outbox_table

SCHEMA = "trips"

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

outbox = outbox_table(metadata)


trip_series = Table(
    "trip_series",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("driver_id", Uuid, nullable=False),
    Column("direction", String(20), nullable=False),
    Column("place_label", String(200), nullable=False),
    Column("place_lat", Float, nullable=False),
    Column("place_lng", Float, nullable=False),
    Column("departure_at", DateTime(timezone=True), nullable=False),
    Column("seats_total", Integer, nullable=False),
    Column("weekdays", JSON, nullable=False),
    Column("end_date", Date, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    CheckConstraint(
        "seats_total BETWEEN 1 AND 6",
        name="valid_series_seats_total",
    ),
    Index("ix_trip_series_driver_id", "driver_id"),
)

trips = Table(
    "trips",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("driver_id", Uuid, nullable=False),
    Column("series_id", Uuid, ForeignKey("trips.trip_series.id"), nullable=True,),
    Column("direction", String(20), nullable=False),
    Column("origin_label", String(200), nullable=False),
    Column("origin_lat", Float, nullable=False),
    Column("origin_lng", Float, nullable=False),
    Column("destination_label", String(200), nullable=False),
    Column("destination_lat", Float, nullable=False),
    Column("destination_lng", Float, nullable=False),
    Column("departure_at", DateTime(timezone=True), nullable=False),
    Column("estimated_arrival_at", DateTime(timezone=True), nullable=False),
    Column("duration_seconds", Integer, nullable=False),
    Column("distance_meters", Integer, nullable=False),
    Column("seats_total", Integer, nullable=False),
    Column("seats_available", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    CheckConstraint(
        "seats_total BETWEEN 1 AND 6",
        name="valid_seats_total",
    ),
    CheckConstraint(
        "seats_available >= 0 AND seats_available <= seats_total",
        name="valid_seats_available",
    ),
    CheckConstraint(
        "duration_seconds >= 0 AND distance_meters >= 0",
        name="valid_route_metrics",
    ),
    Index("ix_trips_driver_departure", "driver_id", "departure_at"),
)
