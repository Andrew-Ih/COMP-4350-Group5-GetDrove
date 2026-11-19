"""Join the payment-failure consumer (a15300000001) and approved-drivers (#11) histories.

Both came after b15d20261116 on different branches: a15300000001 on develop, and
3a27a63e51c5 (which already joins #11's 5529ada83545) on story #8's branch. This revision only
marks that both come before it.

Revision ID: 27e792f1d884
Revises: a15300000001, 3a27a63e51c5
"""

revision = "27e792f1d884"
down_revision = ("a15300000001", "3a27a63e51c5")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
