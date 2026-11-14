"""SQLAlchemy table definitions for the trips schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
    text,
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

trips = Table(
    "trips",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("driver_id", Uuid, nullable=False),
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

seat_requests = Table(
    "seat_requests",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "trip_id",
        Uuid,
        ForeignKey("trips.trips.id"),
        nullable=False,
    ),
    Column("rider_id", Uuid, nullable=False),
    Column("status", String(20), nullable=False),
    Column("pickup_label", String(200), nullable=False),
    Column("pickup_lat", Float, nullable=False),
    Column("pickup_lng", Float, nullable=False),
    Column("walk_seconds", Integer, nullable=False),
    Column("rider_distance_meters", Integer, nullable=False),
    Column("detour_seconds", Integer, nullable=True),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("cost_explanation", String(1000), nullable=False),
    Column(
        "auto_accepted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("decided_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired', 'payment_failed')",
        name="valid_request_status",
    ),
    CheckConstraint(
        "length(trim(pickup_label)) > 0",
        name="valid_pickup_label",
    ),
    CheckConstraint(
        "pickup_lat BETWEEN -90 AND 90 AND pickup_lng BETWEEN -180 AND 180",
        name="valid_pickup_coordinates",
    ),
    CheckConstraint(
        "walk_seconds >= 0 AND rider_distance_meters >= 0",
        name="valid_request_metrics",
    ),
    CheckConstraint(
        "detour_seconds IS NULL OR detour_seconds >= 0",
        name="valid_detour_seconds",
    ),
    CheckConstraint(
        "amount_cents >= 0 AND currency = 'CAD'",
        name="valid_request_cost",
    ),
    CheckConstraint(
        "decided_at IS NULL OR decided_at >= created_at",
        name="valid_decision_time",
    ),
    Index(
        "uq_seat_requests_active_trip_rider",
        "trip_id",
        "rider_id",
        unique=True,
        postgresql_where=text("status IN ('pending', 'accepted')"),
    ),
    Index("ix_seat_requests_rider_created", "rider_id", "created_at"),
)
