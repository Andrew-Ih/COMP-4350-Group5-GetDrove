"""create trip_members table

Revision ID: 3218996b168e
Revises: 89cca62cd76d
Create Date: 2026-11-15 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '3218996b168e'
down_revision: str | None = '89cca62cd76d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('trip_members',
    sa.Column('trip_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('driver', 'rider')", name=op.f('ck_trip_members_valid_role')),
    sa.PrimaryKeyConstraint('trip_id', 'user_id', name=op.f('pk_trip_members')),
    schema='notifications'
    )


def downgrade() -> None:
    op.drop_table('trip_members', schema='notifications')
