"""create tenant schema and tenant table with RLS

Revision ID: 0242df1a3871
Revises: 574dc291c82c
Create Date: 2026-08-09 15:52:00.000000

The first business-adjacent table. Deliberately minimal — this is Phase 2's
"minimum tenant infrastructure required by the architecture", not a Tenant
Administration feature (no branch/warehouse/cylinder_type, which the
`tenant` schema will eventually also hold per `06-database-architecture.md`
§3; those arrive with the phase that needs them).

**`tenant.tenant` deliberately has no `tenant_id` column.** Per
§5's standard-column table, every business table carries one — but a tenant
cannot belong to another tenant, so this table is the same kind of
documented exception `identity.identity_user` already is for Super Admin.
Its own `id` **is** the discriminator: the RLS policy predicates directly on
`id = current_setting('app.current_tenant_id')`, so a tenant-scoped
connection can see (and update) only its own row, never another tenant's.

That design has a real consequence worth stating plainly: **no row can be
inserted through a tenant-scoped connection**, because before a tenant
exists there is no session tenant context that could satisfy the check —
`WITH CHECK` on an ALL-commands policy defaults to the same expression as
`USING`. This is correct, not a bug: tenant provisioning is inherently a
platform/admin operation (out of Phase 2's scope — "do not implement tenant
administration"), never something the ordinary tenant-scoped application
path performs. Seed rows are created directly by the elevated migration
role, exactly as `tests/tenant_isolation` does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0242df1a3871"
down_revision: str | None = "574dc291c82c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "tenant"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        _TABLE,
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("slug", name="uq_tenant_slug"),
        schema=_SCHEMA,
    )

    # RLS — created in the same migration as the table it protects, never out
    # of band (06-database-architecture.md §10).
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_tenant_tenant_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    # Application role gets the standard baseline (SELECT/INSERT are already
    # granted by ALTER DEFAULT PRIVILEGES in 01-init.sql for locally-created
    # tables; UPDATE/DELETE are granted explicitly here since the default
    # privileges deliberately withhold them — see 01-init.sql's comment on
    # append-only tables). tenant.tenant is not append-only: renaming a
    # tenant is a legitimate, RLS-protected update to your own row.
    #
    # DELETE is granted deliberately, for one reason only: the tenant
    # -isolation test suite (`tests/tenant_isolation/`) needs a real DELETE
    # privilege to exist so that "another tenant's row cannot be deleted" is
    # proven by **RLS filtering the row out**, not merely by the role lacking
    # DELETE entirely — the latter would prove nothing about RLS.
    #
    # The application role differs per database — lpg_app for lpg_dev/
    # lpg_test, lpg_app_uat for lpg_uat, and (eventually) a dedicated
    # NOSUPERUSER/NOBYPASSRLS Supabase role for production (DW-19) — so the
    # grant target is resolved from current_database() rather than hardcoded,
    # letting this one migration apply correctly everywhere it runs.
    op.execute(f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {_SCHEMA} TO %I', app_role);
                EXECUTE format(
                    'GRANT SELECT, UPDATE, DELETE ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_tenant_tenant_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
