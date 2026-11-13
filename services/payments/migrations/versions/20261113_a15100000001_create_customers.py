"""Create customer mappings; card details stay in Stripe.

Revision ID: a15100000001
Revises: None
"""

import sqlalchemy as sa
from alembic import op

revision = "a15100000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("default_payment_method_id", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("user_id", name="pk_customers"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_customers_stripe_customer_id"),
        schema="payments",
    )


def downgrade() -> None:
    op.drop_table("customers", schema="payments")
