"""Alembic environment for the routing service (async, own schema)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from routing.adapters.persistence.tables import SCHEMA, metadata
from routing.infrastructure.settings import get_settings

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
    """Autogenerate only looks at the routing schema. Otherwise it finds PostGIS's tables
    (public.spatial_ref_sys, the tiger and topology schemas) and other services' schemas,
    and writes migrations that drop them, or fails on schemas this user can't read."""
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
        # Writes GeoAlchemy2's Geometry columns correctly in generated migrations.
        render_item=alembic_helpers.render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # The routing user's default schema is routing (search_path "routing, public").
        # Alembic then reports those tables without a schema, while ours name it. Starting
        # from public makes it see routing by name, as in the accounts service.
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
