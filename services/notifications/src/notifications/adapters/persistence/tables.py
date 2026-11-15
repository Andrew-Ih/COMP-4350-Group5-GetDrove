"""SQLAlchemy table definitions for the notifications schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)

from events.consumer import consumer_tables
from notifications.domain.reminders import ReminderStatus, ScheduledNotificationType

SCHEMA = "notifications"

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

# Which events have been handled (so a repeat delivery is skipped, even after a restart)
# and which kept failing (parked after 5 tries). From libs/events.
consumer = consumer_tables(metadata)

_STATUSES = ", ".join(f"'{status}'" for status in ReminderStatus)
_SCHEDULED_TYPES = ", ".join(f"'{kind}'" for kind in ScheduledNotificationType)

# Notifications waiting to be sent at a set time by the scheduler (#149). So far only trip
# reminders (#148), one per accepted request.
scheduled_notifications = Table(
    "scheduled_notifications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("type", String(30), nullable=False),
    Column("rider_id", Uuid, nullable=False),
    Column("trip_id", Uuid, nullable=False),
    Column("request_id", Uuid, nullable=False),
    Column("departure_at", DateTime(timezone=True), nullable=False),
    Column("pickup_label", Text, nullable=False),
    Column("send_at", DateTime(timezone=True), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(f"status IN ({_STATUSES})", name="valid_status"),
    CheckConstraint(f"type IN ({_SCHEDULED_TYPES})", name="valid_type"),
    # A request accepted twice (a repeated event) still gets one reminder.
    UniqueConstraint("type", "request_id", name="uq_scheduled_notifications_type_request_id"),
    # Cancelling a trip cancels its reminders.
    Index("ix_scheduled_notifications_trip_id", "trip_id"),
    # What the scheduler looks for: pending reminders that are due.
    Index(
        "ix_scheduled_notifications_pending_send_at",
        "send_at",
        postgresql_where=text("status = 'pending'"),
    ),
)
