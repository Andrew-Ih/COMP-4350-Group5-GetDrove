"""Payment holds, transactional outbox and consumer deduplication (#70).
Revision ID: a70000000001
Revises: None
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "a70000000001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("payment_holds",
        sa.Column("request_id", sa.Uuid(), primary_key=True),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("rider_id", sa.Uuid(), nullable=False),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stripe_id", sa.String(255), unique=True),
        sa.Column("customer_id", sa.String(255)),
        sa.Column("payment_method_id", sa.String(255)),
        sa.Column("first_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("retry_at", sa.DateTime(timezone=True)),
        sa.Column("correlation_id", sa.String(255)),
        sa.CheckConstraint("amount_cents > 0 AND currency = 'CAD'", name="valid_saved_amount"),
        sa.CheckConstraint("status IN ('SCHEDULED','AUTHORIZED','CAPTURED','RELEASED','FAILED')", name="valid_hold_status"),
        sa.CheckConstraint("(customer_id IS NULL) = (payment_method_id IS NULL)", name="complete_card_reference"),
        schema="payments")
    op.create_index("ix_payment_holds_due", "payment_holds", ["status", "retry_at"], schema="payments")
    op.create_table("outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("type", sa.String(200), nullable=False),
        sa.Column("envelope", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True)), schema="payments")
    op.create_index("ix_outbox_unpublished", "outbox", ["id"],
        postgresql_where=sa.text("published_at IS NULL"), schema="payments")
    op.create_table("processed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(200), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="payments")
    op.create_table("failed_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(200), nullable=False),
        sa.Column("stream", sa.String(200), nullable=False),
        sa.Column("envelope", postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="payments")

def downgrade() -> None:
    for table in ("failed_events", "processed_events", "outbox", "payment_holds"):
        op.drop_table(table, schema="payments")
