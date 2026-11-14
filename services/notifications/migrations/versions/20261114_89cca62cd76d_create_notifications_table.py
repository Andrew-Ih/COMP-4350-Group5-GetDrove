"""create notifications table

Revision ID: 89cca62cd76d
Revises: 2fbb4481a682
Create Date: 2026-11-14 13:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '89cca62cd76d'
down_revision: str | None = '2fbb4481a682'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('trip_id', sa.Uuid(), nullable=True),
    sa.Column('request_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("type IN ('seat_requested', 'request_accepted', 'request_declined', 'request_cancelled', 'trip_cancelled', 'driver_approved', 'driver_rejected', 'payment_failed', 'trip_reminder')", name=op.f('ck_notifications_valid_type')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    schema='notifications'
    )
    op.create_index('ix_notifications_user_id_created_at', 'notifications', ['user_id', 'created_at'], unique=False, schema='notifications')


def downgrade() -> None:
    op.drop_index('ix_notifications_user_id_created_at', table_name='notifications', schema='notifications')
    op.drop_table('notifications', schema='notifications')
