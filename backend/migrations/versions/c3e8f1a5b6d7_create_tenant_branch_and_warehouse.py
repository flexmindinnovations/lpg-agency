"""create tenant.branch and tenant.warehouse tables with RLS

Revision ID: c3e8f1a5b6d7
Revises: b1c4a9e7d2f3
Create Date: 2026-08-10 16:20:00.000000

Phase 7's first real master-data tables — `docs/data/03-database-schema.md`
has documented their shape since Phase 0; nothing has created them until now.
Standard tenant-scoped RLS (the ordinary `tenant_id = current_setting(...)`
predicate every business table since Phase 2 uses), **not** `tenant.tenant`'s
self-referential pattern — a branch genuinely belongs to a tenant, it isn't
one.

Also adds the foreign key Phase 6 deliberately left dangling:
`identity.identity_user.branch_id` has existed as a plain, unconstrained
`uuid` column since migration `fa52b77ec442` (no branch table existed yet to
reference) — this migration adds the real `REFERENCES tenant.branch(id)`
now that one does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c3e8f1a5b6d7"
down_revision: str | None = "b1c4a9e7d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"


def _standard_columns() -> list[sa.Column]:
    """The audit-column set every table in this codebase carries
    (`docs/data/03-database-schema.md` §"Every table carries these"),
    matching every prior migration's exact shape.
    """
    return [
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
    ]


def _grant(*, table: str, privileges: str) -> str:
    """The dynamic per-database role-detection grant block, identical shape
    to every prior migration's — resolved from `current_database()` rather
    than hardcoded so one migration applies correctly on lpg_dev/lpg_test
    (`lpg_app`) and lpg_uat (`lpg_app_uat`) alike.
    """
    return f"""
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
                    'GRANT {privileges} ON {_SCHEMA}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING ({_TENANT_RLS_PREDICATE})
    """)


_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        "branch",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.tenant.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=200), nullable=True),
        *_standard_columns(),
        schema=_SCHEMA,
    )
    op.create_index("idx_branch_tenant_id", "branch", ["tenant_id"], schema=_SCHEMA)
    _enable_rls("branch")
    op.execute(_grant(table="branch", privileges="SELECT, INSERT, UPDATE"))

    op.create_table(
        "warehouse",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.branch.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address_line", sa.String(length=500), nullable=False),
        *_standard_columns(),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_warehouse_tenant_branch", "warehouse", ["tenant_id", "branch_id"], schema=_SCHEMA
    )
    _enable_rls("warehouse")
    op.execute(_grant(table="warehouse", privileges="SELECT, INSERT, UPDATE"))

    # The FK Phase 6 left dangling — `identity.identity_user.branch_id` has
    # existed as a plain, unconstrained uuid since `fa52b77ec442`.
    op.create_foreign_key(
        "fk_identity_user_branch_id",
        "identity_user",
        "branch",
        ["branch_id"],
        ["id"],
        source_schema="identity",
        referent_schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_identity_user_branch_id", "identity_user", schema="identity", type_="foreignkey"
    )
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_warehouse_isolation ON {_SCHEMA}.warehouse")
    op.drop_table("warehouse", schema=_SCHEMA)
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_branch_isolation ON {_SCHEMA}.branch")
    op.drop_table("branch", schema=_SCHEMA)
