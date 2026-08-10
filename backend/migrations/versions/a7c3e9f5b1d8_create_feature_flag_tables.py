"""create platform.feature_flag and tenant.feature_flag_override tables

Revision ID: a7c3e9f5b1d8
Revises: f6b2d8e4a0c7
Create Date: 2026-08-10 17:40:00.000000

The user chose a **full** feature-flag system (platform-wide flags +
tenant-level overrides + percentage rollout + scheduling) over a simple
per-tenant boolean table — see
`planning/features/07-administration-tenant-master-data/PLAN.md`.

**`platform.feature_flag` is a new schema, deliberately not RLS-scoped** —
a flag definition is genuinely cross-tenant, the same non-RLS-reference-data
precedent `identity.role`/`identity.permission` already established (Phase
6). Write access is restricted at the **application layer**
(`require_live_permission("feature_flags:manage_platform")`, super_admin
only, live-checked), not by database grants — this codebase's application
role always connects as the same `lpg_app`/`lpg_app_uat` regardless of the
authenticated user's role; every permission decision in this system is
enforced above the database, in the use case/API layer, consistent with
every other RBAC check here.

`tenant.feature_flag_override` is a normal tenant-scoped RLS table — an
explicit override always wins over the platform default/rollout when a
tenant has one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "a7c3e9f5b1d8"
down_revision: str | None = "f6b2d8e4a0c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLATFORM_SCHEMA = "platform"
_TENANT_SCHEMA = "tenant"


def _standard_columns() -> list[sa.Column]:
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


def _grant(*, schema: str, table: str, privileges: str) -> str:
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format('GRANT USAGE ON SCHEMA {schema} TO %I', app_role);
                EXECUTE format(
                    'GRANT {privileges} ON {schema}.{table} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_PLATFORM_SCHEMA}")

    op.create_table(
        "feature_flag",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column(
            "is_enabled_by_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("rollout_percentage", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        *_standard_columns(),
        sa.CheckConstraint(
            "rollout_percentage IS NULL OR rollout_percentage BETWEEN 0 AND 100",
            name="ck_feature_flag_rollout_percentage_range",
        ),
        schema=_PLATFORM_SCHEMA,
    )
    # No RLS — genuinely cross-tenant, see module docstring. SELECT is
    # needed by every request (evaluating flags); INSERT/UPDATE are granted
    # too, since the application role is what actually executes the write on
    # behalf of a super_admin-authorized request — the authorization check
    # itself happens in the use case, not at the grant level (see module
    # docstring).
    op.execute(
        _grant(schema=_PLATFORM_SCHEMA, table="feature_flag", privileges="SELECT, INSERT, UPDATE")
    )

    op.create_table(
        "feature_flag_override",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"),
            nullable=False,
        ),
        sa.Column(
            "flag_key",
            sa.String(length=100),
            sa.ForeignKey(f"{_PLATFORM_SCHEMA}.feature_flag.key"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *_standard_columns(),
        sa.UniqueConstraint("tenant_id", "flag_key", name="uq_feature_flag_override_tenant_flag"),
        schema=_TENANT_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_TENANT_SCHEMA}.feature_flag_override ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TENANT_SCHEMA}.feature_flag_override FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_TENANT_SCHEMA}_feature_flag_override_isolation
        ON {_TENANT_SCHEMA}.feature_flag_override
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)
    op.execute(
        _grant(
            schema=_TENANT_SCHEMA,
            table="feature_flag_override",
            privileges="SELECT, INSERT, UPDATE",
        )
    )


def downgrade() -> None:
    op.execute(
        f"DROP POLICY IF EXISTS rls_{_TENANT_SCHEMA}_feature_flag_override_isolation "
        f"ON {_TENANT_SCHEMA}.feature_flag_override"
    )
    op.drop_table("feature_flag_override", schema=_TENANT_SCHEMA)
    op.drop_table("feature_flag", schema=_PLATFORM_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_PLATFORM_SCHEMA}")
