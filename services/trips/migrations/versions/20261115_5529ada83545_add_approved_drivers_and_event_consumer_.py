"""add approved drivers and event consumer tables

Revision ID: 5529ada83545
Revises: 682e9335a989
Create Date: 2026-11-15 01:27:34.054782
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '5529ada83545'
down_revision: str | None = '682e9335a989'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Students approved to drive (#11), filled from Accounts' events.
    op.create_table(
        "approved_drivers",
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("driver_id", name=op.f("pk_approved_drivers")),
        schema="trips",
    )
    # libs/events consumer tables: events handled once, and events that kept failing.
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=200), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_processed_events")),
        schema="trips",
    )
    op.create_table(
        "failed_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=200), nullable=False),
        sa.Column("stream", sa.String(length=200), nullable=False),
        sa.Column("envelope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "failed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_failed_events")),
        schema="trips",
    )


def downgrade() -> None:
    op.drop_table("failed_events", schema="trips")
    op.drop_table("processed_events", schema="trips")
    op.drop_table("approved_drivers", schema="trips")
