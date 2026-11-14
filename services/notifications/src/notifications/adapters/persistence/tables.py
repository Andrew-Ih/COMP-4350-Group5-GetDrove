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
    Uuid,
)

from events.consumer import consumer_tables
from notifications.domain.notifications import NotificationType

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

_TYPES = ", ".join(f"'{value}'" for value in NotificationType)

# In-app notifications, shown in the bell (#145). Only the user they're for can read them.
notifications = Table(
    "notifications",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Uuid, nullable=False),
    Column("type", String(30), nullable=False),
    Column("title", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("trip_id", Uuid, nullable=True),
    Column("request_id", Uuid, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("read_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(f"type IN ({_TYPES})", name="valid_type"),
    # The bell lists a user's newest notifications.
    Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
)
