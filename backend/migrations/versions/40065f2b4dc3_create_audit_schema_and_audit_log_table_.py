"""create audit schema and audit_log table with RLS

Revision ID: 40065f2b4dc3
Revises: 0242df1a3871
Create Date: 2026-08-09 16:40:00.000000

Per `06-database-architecture.md` §6: append-only, captures actor, tenant,
entity, action, and before/after state. Phase 2 instructions additionally
require `correlation_id`, tying an audit row back to the request that
produced it.

**Immutability is enforced by the database, not application discipline.**
The application role gets `SELECT, INSERT` only — no `UPDATE`, no `DELETE`.
An audit trail the application can rewrite is not an audit trail.

RLS follows the standard (non-self-referential) pattern every future
tenant-scoped table will use: `tenant_id = current_setting(...)`. Unlike
`tenant.tenant`, `tenant_id` here is **nullable** — a documented exception
for audit rows about actions with no resolved tenant context (Phase 2 has
none yet, but the column must not force one prematurely). A NULL tenant_id
row is invisible to every tenant-scoped connection, by construction of the
policy (`NULL = anything` is never true) — the conservative default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "40065f2b4dc3"
down_revision: str | None = "0242df1a3871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "audit"
_TABLE = "audit_log"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("entity_name", sa.String(length=200), nullable=False),
        sa.Column("entity_id", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_audit_log_tenant_entity",
        _TABLE,
        ["tenant_id", "entity_name", "entity_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_audit_log_performed_at",
        _TABLE,
        ["performed_at"],
        schema=_SCHEMA,
    )

    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_audit_log_tenant_isolation ON {_SCHEMA}.{_TABLE}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)

    # Same per-database role resolution as migration 0242df1a3871 — see that
    # migration's comment for why this can't be hardcoded to `lpg_app`.
    # SELECT + INSERT only: no UPDATE, no DELETE, ever, for any role except
    # the migration/admin role — immutability is the entire point.
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
                    'GRANT SELECT, INSERT ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_audit_log_tenant_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
