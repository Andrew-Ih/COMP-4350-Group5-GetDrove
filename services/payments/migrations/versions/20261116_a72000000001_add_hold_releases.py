"""Durable release requests and cancellation tombstones (#72).
Revision ID: a72000000001
Revises: a70000000001
"""
import sqlalchemy as sa
from alembic import op

revision = "a72000000001"
down_revision = "a70000000001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("payment_holds", sa.Column("release_requested", sa.Boolean(),
        nullable=False, server_default=sa.false()), schema="payments")
    op.create_table("cancelled_requests",
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("rider_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False), schema="payments")
    op.create_table("cancelled_trips",
        sa.Column("trip_id", sa.Uuid(), primary_key=True),
        sa.Column("driver_id", sa.Uuid(), nullable=False), schema="payments")

def downgrade() -> None:
    op.drop_table("cancelled_trips", schema="payments")
    op.drop_table("cancelled_requests", schema="payments")
    op.drop_column("payment_holds", "release_requested", schema="payments")
