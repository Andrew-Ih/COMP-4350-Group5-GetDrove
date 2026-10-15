"""SQLAlchemy table definitions for the accounts schema.

Every table belongs to this service's own Postgres schema; no other service reads it.
Alembic autogenerates migrations from ``metadata``.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Uuid,
    false,
    func,
)

from events.outbox import outbox_table

SCHEMA = "accounts"

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

users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    # Stored lowercase (the domain normalizes it), so the unique constraint is
    # case-insensitive in practice. A duplicate becomes the 409 email_taken error.
    Column("email", String(254), nullable=False, unique=True),
    # Argon2id hash (ADR 0020); never the password itself.
    Column("password_hash", String(255), nullable=False),
    Column("first_name", String(50), nullable=False),
    Column("last_name", String(50), nullable=False),
    # Null until the student clicks the verification link; the API's emailVerified
    # is "email_verified_at is not null".
    Column("email_verified_at", DateTime(timezone=True), nullable=True),
    # Every account is a "user"; this adds "admin" to the roles (Sprint 2).
    Column("is_admin", Boolean, nullable=False, server_default=false()),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
)

# Both token tables store only the SHA-256 hash of the token we send; the token
# itself is never saved.

verification_tokens = Table(
    "verification_tokens",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "user_id",
        Uuid,
        ForeignKey(users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    # Set when the link is used or a resend replaces it. Used rows are kept, not
    # deleted, so /auth/verify can tell "already used" (400) from "expired" (410).
    Column("consumed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "user_id",
        Uuid,
        ForeignKey(users.c.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    # Set on logout, or when /auth/refresh swaps this token for a new one.
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    # The token that replaced this one. Someone presenting a replaced token is
    # reusing a stolen one, so that user's sessions are ended.
    Column(
        "replaced_by_id",
        Uuid,
        ForeignKey(f"{SCHEMA}.refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

# Events waiting to be sent to Redis (libs/events). Saved in the same transaction as
# the change that caused them, e.g. UserRegistered with the new user.
outbox = outbox_table(metadata)
