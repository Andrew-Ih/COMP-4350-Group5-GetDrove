
"""Add recurring trip series schema.

Revision ID: a16b20261113
Revises: 682e9335a989
"""

from alembic import op
import sqlalchemy as sa


revision = "a16b20261113"
down_revision = "682e9335a989"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_series",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("place_label", sa.String(200), nullable=False),
        sa.Column("place_lat", sa.Float(), nullable=False),
        sa.Column("place_lng", sa.Float(), nullable=False),
        sa.Column(
            "departure_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("seats_total", sa.Integer(), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "seats_total BETWEEN 1 AND 6",
            name="ck_trip_series_valid_series_seats_total",
        ),
        schema="trips",
    )

    op.create_index(
        "ix_trip_series_driver_id",
        "trip_series",
        ["driver_id"],
        schema="trips",
    )

    op.add_column(
        "trips",
        sa.Column("series_id", sa.Uuid(), nullable=True),
        schema="trips",
    )

    op.create_foreign_key(
        "fk_trips_series_id_trip_series",
        "trips",
        "trip_series",
        ["series_id"],
        ["id"],
        source_schema="trips",
        referent_schema="trips",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_trips_series_id_trip_series",
        "trips",
        type_="foreignkey",
        schema="trips",
    )

    op.drop_column(
        "trips",
        "series_id",
        schema="trips",
    )

    op.drop_index(
        "ix_trip_series_driver_id",
        table_name="trip_series",
        schema="trips",
    )

    op.drop_table(
        "trip_series",
        schema="trips",
    )
