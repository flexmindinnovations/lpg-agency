"""create ai.feature_snapshot table

Revision ID: e3d5c5bb9389
Revises: f25f9f8fa701
Create Date: 2026-09-10

The point-in-time feature store (AI Operational Intelligence — Horizon 1,
Stage 1a). `rpt.mv_customer_consumption` and friends already materialise
current-state aggregates; this table exists because a model must see
features *as they were on the prediction date*, which a materialized view
(always current) cannot give — training-serving skew is the defect Phase
21's PLAN.md calls out to design against.

  - `ai.feature_snapshot` — `(tenant_id, entity_type, entity_id,
    as_of_date) -> features jsonb`. One row per entity per day, written by
    the nightly `build_feature_snapshots` job. `entity_type` is
    "customer_refill" | "branch_cylinder_demand" | "route_stop_duration"
    (free-form string, not a CHECK — new feature families add rows without
    a migration). Append-only (`SELECT, INSERT` grants only): a day's
    snapshot is history, never rewritten; the unique constraint makes the
    job's re-run idempotent via `ON CONFLICT DO NOTHING`.

Follows `b3e97f4d1c6a_create_ai_schema_assistant_run_table.py` / the sibling
`f25f9f8fa701` migration (the `ai` schema already exists; reuse the same
`_grant()` / `_enable_rls()` helpers and the append-only grant).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "e3d5c5bb9389"
down_revision: str | None = "f25f9f8fa701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "ai"
_TENANT_SCHEMA = "tenant"
_TABLE = "feature_snapshot"


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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_{table}_isolation ON {_SCHEMA}.{table}
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        )
    """)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_type",
            "entity_id",
            "as_of_date",
            name="uq_ai_feature_snapshot_dimension",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_ai_feature_snapshot_lookup",
        _TABLE,
        ["tenant_id", "entity_type", "entity_id", "as_of_date"],
        schema=_SCHEMA,
    )

    _enable_rls(_TABLE)
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT"))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
