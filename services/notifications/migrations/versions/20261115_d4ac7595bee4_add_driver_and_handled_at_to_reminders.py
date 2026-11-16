"""add driver and handled_at to scheduled_notifications

Sending reminders (#149) names the driver and records when each was sent or skipped. Both
nullable: reminders stored before have no driver, and pending ones aren't handled yet.

Revision ID: d4ac7595bee4
Revises: c01e37ab4dca
Create Date: 2026-11-15 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4ac7595bee4'
down_revision: str | None = 'c01e37ab4dca'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('scheduled_notifications', sa.Column('driver_id', sa.Uuid(), nullable=True), schema='notifications')
    op.add_column('scheduled_notifications', sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True), schema='notifications')


def downgrade() -> None:
    op.drop_column('scheduled_notifications', 'handled_at', schema='notifications')
    op.drop_column('scheduled_notifications', 'driver_id', schema='notifications')
