"""SQLAlchemy table definitions for the payments schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
)

from events.consumer import consumer_tables
from events.outbox import outbox_table

SCHEMA = "payments"

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


payment_holds = Table(
    "payment_holds",
    metadata,
    Column("request_id", Uuid, primary_key=True),
    Column("trip_id", Uuid, nullable=False),
    Column("rider_id", Uuid, nullable=False),
    Column("driver_id", Uuid, nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("departure_at", DateTime(timezone=True), nullable=False),
    Column("authorize_at", DateTime(timezone=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("stripe_id", String(255), unique=True),
    Column("release_requested", Boolean, nullable=False, server_default="false"),
    Column("customer_id", String(255)),
    Column("payment_method_id", String(255)),
    Column("first_attempt_at", DateTime(timezone=True)),
    Column("retry_at", DateTime(timezone=True)),
    Column("correlation_id", String(255)),
    CheckConstraint("amount_cents > 0 AND currency = 'CAD'", name="valid_saved_amount"),
    CheckConstraint(
        "status IN ('SCHEDULED','AUTHORIZED','CAPTURED','RELEASED','FAILED')",
        name="valid_hold_status",
    ),
    CheckConstraint(
        "(customer_id IS NULL) = (payment_method_id IS NULL)", name="complete_card_reference"
    ),
    Index("ix_payment_holds_due", "status", "retry_at"),
)
outbox = outbox_table(metadata)
consumer = consumer_tables(metadata)


cancelled_requests = Table(
    "cancelled_requests",
    metadata,
    Column("request_id", Uuid, primary_key=True),
    Column("trip_id", Uuid, nullable=False),
    Column("rider_id", Uuid, nullable=False),
    Column("driver_id", Uuid, nullable=False),
)
cancelled_trips = Table(
    "cancelled_trips",
    metadata,
    Column("trip_id", Uuid, primary_key=True),
    Column("driver_id", Uuid, nullable=False),
)


customers = Table(
    "customers",
    metadata,
    Column("user_id", Uuid, primary_key=True),
    Column("stripe_customer_id", String(255), unique=True, nullable=True),
    Column("default_payment_method_id", String(255), nullable=True),
)
