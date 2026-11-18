"""add approved drivers (#11)

Revision ID: 5529ada83545
Revises: 682e9335a989
Create Date: 2026-11-15 01:27:34.054782
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

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
    # The libs/events consumer tables (processed_events, failed_events) used to be created here
    # too. develop's a15300000001 (payment failures) creates them, so they're left to it: Trips
    # has one consumer for both, and creating them twice would fail.


def downgrade() -> None:
    op.drop_table("approved_drivers", schema="trips")
