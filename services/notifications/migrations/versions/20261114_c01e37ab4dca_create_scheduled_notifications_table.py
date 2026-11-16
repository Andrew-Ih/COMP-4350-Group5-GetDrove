"""create scheduled_notifications table

Revision ID: c01e37ab4dca
Revises: 3218996b168e
Create Date: 2026-11-14 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c01e37ab4dca'
down_revision: str | None = '3218996b168e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('scheduled_notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('rider_id', sa.Uuid(), nullable=False),
    sa.Column('trip_id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('departure_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('pickup_label', sa.Text(), nullable=False),
    sa.Column('send_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'sent', 'skipped', 'cancelled')", name=op.f('ck_scheduled_notifications_valid_status')),
    sa.CheckConstraint("type IN ('trip_reminder')", name=op.f('ck_scheduled_notifications_valid_type')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scheduled_notifications')),
    sa.UniqueConstraint('type', 'request_id', name='uq_scheduled_notifications_type_request_id'),
    schema='notifications'
    )
    op.create_index('ix_scheduled_notifications_trip_id', 'scheduled_notifications', ['trip_id'], unique=False, schema='notifications')
    op.create_index('ix_scheduled_notifications_pending_send_at', 'scheduled_notifications', ['send_at'], unique=False, schema='notifications', postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index('ix_scheduled_notifications_pending_send_at', table_name='scheduled_notifications', schema='notifications', postgresql_where=sa.text("status = 'pending'"))
    op.drop_index('ix_scheduled_notifications_trip_id', table_name='scheduled_notifications', schema='notifications')
    op.drop_table('scheduled_notifications', schema='notifications')
