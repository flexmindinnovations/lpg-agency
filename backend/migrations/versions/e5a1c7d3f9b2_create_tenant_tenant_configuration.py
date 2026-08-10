"""create tenant.tenant_configuration table with RLS

Revision ID: e5a1c7d3f9b2
Revises: d4f9a2b8e1c6
Create Date: 2026-08-10 17:00:00.000000

Historized tenant-scoped configuration (BR-31) — GST rate, cancellation fee,
credit limit defaults, and whatever future config keys later phases add.
Rows are never updated once written; "changing" a value means inserting a
new row with a later `effective_from`, so a past transaction can always be
re-evaluated against the value that was actually in effect at the time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e5a1c7d3f9b2"
down_revision: str | None = "d4f9a2b8e1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "tenant_configuration"


def _grant(*, table: str, privileges: str) -> str:
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


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.tenant.id"),
            nullable=False,
        ),
        sa.Column("config_key", sa.String(length=100), nullable=False),
        sa.Column("config_value", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        # No updated_at/updated_by/is_deleted/deleted_at/deleted_by/version —
        # this table is append-only by design (see module docstring); the
        # standard mutable-row audit columns don't apply to a row that is
        # never mutated or deleted.
        sa.UniqueConstraint(
            "tenant_id", "config_key", "effective_from", name="uq_tenant_config_key_effective"
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_tenant_configuration_tenant_key",
        _TABLE,
        ["tenant_id", "config_key"],
        schema=_SCHEMA,
    )

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)
    # SELECT/INSERT only — no UPDATE/DELETE grant, enforcing "append-only" at
    # the database role level too, not just by convention (matching
    # audit.audit_log's own enforcement shape from Phase 2).
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT"))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
