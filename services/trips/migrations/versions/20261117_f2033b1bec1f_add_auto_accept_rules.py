"""add auto-accept rules

Revision ID: f2033b1bec1f
Revises: b15d20261116
Create Date: 2026-11-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f2033b1bec1f'
down_revision: str | None = 'b15d20261116'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('auto_accept_rules',
    sa.Column('driver_id', sa.Uuid(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('max_detour_minutes', sa.Integer(), nullable=False),
    sa.Column('min_rating', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('max_detour_minutes BETWEEN 0 AND 30', name=op.f('ck_auto_accept_rules_valid_max_detour')),
    sa.CheckConstraint('min_rating IS NULL OR min_rating BETWEEN 1 AND 5', name=op.f('ck_auto_accept_rules_valid_min_rating')),
    sa.PrimaryKeyConstraint('driver_id', name=op.f('pk_auto_accept_rules')),
    schema='trips'
    )


def downgrade() -> None:
    op.drop_table('auto_accept_rules', schema='trips')
