"""Persist the planned authorization time for far-ahead bookings (#154)."""

import sqlalchemy as sa
from alembic import op

revision = "a15400000001"
down_revision = "a72000000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_holds",
        sa.Column("authorize_at", sa.DateTime(timezone=True), nullable=True),
        schema="payments",
    )
    # Preserve existing work and reconciliation state; do not restart old authorizations.
    op.execute("""
        UPDATE payments.payment_holds
        SET authorize_at = COALESCE(first_attempt_at, retry_at, departure_at)
    """)
    op.alter_column("payment_holds", "authorize_at", nullable=False, schema="payments")


def downgrade() -> None:
    op.drop_column("payment_holds", "authorize_at", schema="payments")
