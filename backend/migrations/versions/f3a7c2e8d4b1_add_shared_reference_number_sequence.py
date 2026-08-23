"""add shared reference number sequence

Revision ID: f3a7c2e8d4b1
Revises: a3f6c8d1b7e5
Create Date: 2026-08-21 12:00:00.000000

A single, shared, tenant-scoped counter table backing the human-readable
reference numbers introduced across every module in this migration series
(`INV000001`, `ORD000001`, `CMP000001`, `EMP0001`, ...), keyed on
`(tenant_id, entity_type)`.

This generalizes `customer.customer_number_sequence`
(`d2e8f4a6c1b9_add_consumer_number_sequence_and_lpg_id.py`) — the original,
per-module precedent — into one reusable table instead of one dedicated
table per module. `consumer_number` itself is left as-is (already shipped,
in use, no reason to migrate it onto the new shared mechanism).

Lives in `platform`, not any one bounded context's schema — same reasoning
as `platform.feature_flag` (see that model's module docstring): the
persistence-schema boundary, not the bounded-context boundary, decides
where a shared infra table lives. Unlike `feature_flag`, this table *is*
RLS-scoped (every caller is a tenant-scoped app request), using the same
`_TENANT_RLS_PREDICATE`/`_grant()` idiom as `d2e8f4a6c1b9`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f3a7c2e8d4b1"
down_revision: str | None = "a3f6c8d1b7e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "platform"
_TABLE = "reference_number_sequence"

_TENANT_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


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
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("entity_type", sa.String(length=30), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema=_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{_TABLE}_isolation
        ON {_SCHEMA}.{_TABLE}
        USING ({_TENANT_RLS_PREDICATE})
    """)
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT, UPDATE"))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
