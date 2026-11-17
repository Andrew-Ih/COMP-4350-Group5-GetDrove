"""Create seat requests and prevent duplicate active requests.

Revision ID: a13700000001
Revises: 682e9335a989
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a13700000001"
down_revision: str | None = "682e9335a989"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seat_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("rider_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("pickup_label", sa.String(200), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("walk_seconds", sa.Integer(), nullable=False),
        sa.Column("rider_distance_meters", sa.Integer(), nullable=False),
        sa.Column("detour_seconds", sa.Integer(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cost_explanation", sa.String(1000), nullable=False),
        sa.Column(
            "auto_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN "
            "('pending', 'accepted', 'declined', 'cancelled', 'expired', 'payment_failed')",
            name=op.f("ck_seat_requests_valid_request_status"),
        ),
        sa.CheckConstraint(
            "length(trim(pickup_label)) > 0",
            name=op.f("ck_seat_requests_valid_pickup_label"),
        ),
        sa.CheckConstraint(
            "pickup_lat BETWEEN -90 AND 90 AND pickup_lng BETWEEN -180 AND 180",
            name=op.f("ck_seat_requests_valid_pickup_coordinates"),
        ),
        sa.CheckConstraint(
            "walk_seconds >= 0 AND rider_distance_meters >= 0",
            name=op.f("ck_seat_requests_valid_request_metrics"),
        ),
        sa.CheckConstraint(
            "detour_seconds IS NULL OR detour_seconds >= 0",
            name=op.f("ck_seat_requests_valid_detour_seconds"),
        ),
        sa.CheckConstraint(
            "amount_cents >= 0 AND currency = 'CAD'",
            name=op.f("ck_seat_requests_valid_request_cost"),
        ),
        sa.CheckConstraint(
            "decided_at IS NULL OR decided_at >= created_at",
            name=op.f("ck_seat_requests_valid_decision_time"),
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.trips.id"],
            name=op.f("fk_seat_requests_trip_id_trips"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seat_requests")),
        schema="trips",
    )
    op.create_index(
        "uq_seat_requests_active_trip_rider",
        "seat_requests",
        ["trip_id", "rider_id"],
        unique=True,
        schema="trips",
        postgresql_where=sa.text("status IN ('pending', 'accepted')"),
    )
    op.create_index(
        "ix_seat_requests_rider_created",
        "seat_requests",
        ["rider_id", "created_at"],
        unique=False,
        schema="trips",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_seat_requests_rider_created",
        table_name="seat_requests",
        schema="trips",
    )
    op.drop_index(
        "uq_seat_requests_active_trip_rider",
        table_name="seat_requests",
        schema="trips",
    )
    op.drop_table("seat_requests", schema="trips")
