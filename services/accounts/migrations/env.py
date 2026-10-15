"""Alembic environment for the accounts service (async, own schema)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from accounts.adapters.persistence.tables import SCHEMA, metadata
from accounts.infrastructure.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """Autogenerate only looks at the accounts schema. Otherwise it finds PostGIS's tables
    (public.spatial_ref_sys) and other services' schemas, and writes migrations that drop
    them, or fails on schemas this user can't read."""
    if type_ == "schema":
        return name == SCHEMA
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # The accounts user's default schema is accounts (search_path "accounts, public").
        # Alembic then reports those tables without a schema, while ours name it, and
        # autogenerate keeps rewriting the foreign keys. Starting from public makes it see
        # accounts by name. Every table and the version table name their schema anyway.
        connect_args={"server_settings": {"search_path": "public"}},
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
