"""Alembic environment.

Runs migrations against the async engine, reading the connection string from
``LPG_DATABASE_URL`` so no credential is ever committed.

**No migrations exist yet.** Phase 1 establishes the harness only; the first
migration arrives in Phase 2 alongside the first tables. When it does, note
two things carried over from the architecture:

* Migrations run under the *superuser* role, never the application role
  (``06-database-architecture.md`` §2.2).
* RLS policies are created in the same migration as the table they protect —
  never out of band, or an environment will end up with a table whose tenant
  backstop is missing (§10).
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import lpg.infrastructure.persistence.models  # noqa: F401
from lpg.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic compares against this metadata when autogenerating. No ORM models are
# registered in Phase 1, so it is deliberately empty.
target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the migration connection string.

    Prefers ``LPG_MIGRATION_DATABASE_URL`` — migrations run as the elevated
    role over a *direct* connection, not as the application role through a
    transaction pooler (`06-database-architecture.md` §10, ADR-027). Falls back
    to ``LPG_DATABASE_URL``, then alembic.ini, then the local docker compose
    superuser.
    """
    return (
        os.environ.get("LPG_MIGRATION_DATABASE_URL")
        or os.environ.get("LPG_DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_dev"
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting.

    Useful for reviewing exactly what a migration will do before it touches a
    real database — worth doing for anything that alters an RLS policy.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
