"""Payment failure consumer deduplication and failed-event parking (#153).
Revision ID: a15300000001
Revises: a31000000001
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "a15300000001"
down_revision = "a31000000001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("processed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(200), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="trips")
    op.create_table("failed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(200), nullable=False),
        sa.Column("stream", sa.String(200), nullable=False),
        sa.Column("envelope", postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="trips")

def downgrade() -> None:
    op.drop_table("failed_events", schema="trips")
    op.drop_table("processed_events", schema="trips")
