"""Join the approved-drivers (#11) and develop migration histories.

Story #8's branch added approved_drivers while develop added recurring trips and seat
requests, both after 682e9335a989. This revision only marks that both come before it.

Revision ID: 3a27a63e51c5
Revises: 5529ada83545, b15d20261116
"""

revision = "3a27a63e51c5"
down_revision = ("5529ada83545", "b15d20261116")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
