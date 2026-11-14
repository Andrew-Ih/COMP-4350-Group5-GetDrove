"""Keep the pickup order of accepted seat requests (#310).

Revision ID: a31000000001
Revises: a13700000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a31000000001"
down_revision: str | None = "a13700000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "seat_requests",
        sa.Column("detour_position", sa.Integer(), nullable=True),
        schema="trips",
    )
    op.add_column(
        "seat_requests",
        sa.Column("pickup_order", sa.Integer(), nullable=True),
        schema="trips",
    )
    op.create_check_constraint(
        op.f("ck_seat_requests_valid_detour_position"),
        "seat_requests",
        "detour_position IS NULL OR detour_position >= 0",
        schema="trips",
    )
    # Number the requests that are already accepted 1..n per trip, oldest first.
    op.execute(
        """
        UPDATE trips.seat_requests AS target
        SET pickup_order = ranked.place
        FROM (
            SELECT id, row_number() OVER (PARTITION BY trip_id ORDER BY created_at, id) AS place
            FROM trips.seat_requests
            WHERE status = 'accepted'
        ) AS ranked
        WHERE target.id = ranked.id
        """
    )
    op.create_check_constraint(
        op.f("ck_seat_requests_valid_pickup_order"),
        "seat_requests",
        "pickup_order IS NULL OR (status = 'accepted' AND pickup_order >= 1)",
        schema="trips",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_seat_requests_valid_pickup_order"),
        "seat_requests",
        schema="trips",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_seat_requests_valid_detour_position"),
        "seat_requests",
        schema="trips",
        type_="check",
    )
    op.drop_column("seat_requests", "pickup_order", schema="trips")
    op.drop_column("seat_requests", "detour_position", schema="trips")