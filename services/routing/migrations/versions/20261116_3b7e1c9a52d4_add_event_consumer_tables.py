"""add event consumer tables

Which events Routing has handled, and the ones it gave up on (libs/events, #37). The detour
plan cache is freed early by the Trips events Routing consumes.

Revision ID: 3b7e1c9a52d4
Revises: d0eb854f1316
Create Date: 2026-11-16 20:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '3b7e1c9a52d4'
down_revision: str | None = 'd0eb854f1316'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('failed_events',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=200), nullable=False),
    sa.Column('stream', sa.String(length=200), nullable=False),
    sa.Column('envelope', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('failed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_failed_events')),
    schema='routing'
    )
    op.create_table('processed_events',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=200), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('event_id', name=op.f('pk_processed_events')),
    schema='routing'
    )


def downgrade() -> None:
    op.drop_table('processed_events', schema='routing')
    op.drop_table('failed_events', schema='routing')