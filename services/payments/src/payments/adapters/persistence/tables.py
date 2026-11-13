"""SQLAlchemy table definitions for the payments schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import Column, MetaData, String, Table, Uuid

SCHEMA = "payments"

metadata = MetaData(
    schema=SCHEMA,
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)

customers = Table(
    "customers",
    metadata,
    Column("user_id", Uuid, primary_key=True),
    Column("stripe_customer_id", String(255), unique=True, nullable=True),
    Column("default_payment_method_id", String(255), nullable=True),
)
