"""Join the auto-accept rules (#42) and develop migration histories.

feature/41 added auto_accept_rules (f2033b1bec1f) while develop gained story #8 and the
payment-failure consumer, joined in 27e792f1d884. Both came after b15d20261116; this
revision only marks that both come before it.

Revision ID: 7da7a5edbcf9
Revises: f2033b1bec1f, 27e792f1d884
"""

revision = "7da7a5edbcf9"
down_revision = ("f2033b1bec1f", "27e792f1d884")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
