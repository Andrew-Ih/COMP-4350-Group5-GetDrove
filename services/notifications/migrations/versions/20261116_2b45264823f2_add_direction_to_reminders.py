"""add direction to scheduled_notifications

Which way the trip goes, so a reminder calls the rider's point a pickup (to campus) or a
drop-off (leaving campus) (#355). Nullable: reminders stored before don't know it.

Revision ID: 2b45264823f2
Revises: d4ac7595bee4
Create Date: 2026-11-16 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2b45264823f2'
down_revision: str | None = 'd4ac7595bee4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('scheduled_notifications', sa.Column('direction', sa.String(length=20), nullable=True), schema='notifications')
    # Autogenerate doesn't see check constraints added to an existing table.
    op.create_check_constraint(
        op.f('ck_scheduled_notifications_valid_direction'),
        'scheduled_notifications',
        "direction IS NULL OR direction IN ('to_campus', 'from_campus')",
        schema='notifications',
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_scheduled_notifications_valid_direction'), 'scheduled_notifications', type_='check', schema='notifications')
    op.drop_column('scheduled_notifications', 'direction', schema='notifications')
