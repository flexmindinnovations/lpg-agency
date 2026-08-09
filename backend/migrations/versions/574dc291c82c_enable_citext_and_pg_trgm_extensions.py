"""enable citext and pg_trgm extensions

Revision ID: 574dc291c82c
Revises:
Create Date: 2026-08-09 15:47:02.488406

The first migration in this repository. ``pgcrypto`` is not created here: it
is verified present on every target (local Docker, hosted Supabase) already,
and is core to PostgreSQL 13+ for ``gen_random_uuid()`` regardless.

Idempotent (``IF NOT EXISTS``) so this applies cleanly on local DEV/UAT, where
`infrastructure/docker/postgres/init/01-init.sql` already created these
extensions directly — this migration is what makes that a documented,
Alembic-owned fact rather than a Docker-only side effect (``06-database
-architecture.md`` §10: "all schema changes go through Alembic migrations,
no manual schema edits in any environment, ever"). It is what actually
installs them on hosted Supabase, where they are not yet present
(confirmed live, Phase 1) — applied there only on explicit go-ahead, per
Phase 2's DEV/UAT/PROD verification instructions.

Per ``06-database-architecture.md`` §14, extensions live in the
``extensions`` schema on Supabase, not ``public`` — passing ``schema=
"extensions"`` is a no-op on local Docker Postgres (which has no such
schema and defaults to ``public``) only if the schema already exists there
too; local Docker has no ``extensions`` schema, so the schema argument is
conditional on environment. Rather than branch on environment inside a
migration (a maintenance hazard), this migration creates the schema itself
if absent, then targets it explicitly everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "574dc291c82c"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext SCHEMA extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA extensions")


def downgrade() -> None:
    # Extensions are never dropped by a migration downgrade: other objects
    # may depend on citext/pg_trgm types and operators by the time a
    # downgrade is contemplated, and DROP EXTENSION would cascade into data
    # loss territory for a decision this migration cannot see the
    # consequences of. Reversing this is a deliberate, reviewed action, not
    # an automated one.
    pass
