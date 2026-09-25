"""create tenant.price_list_proposal table with RLS

Revision ID: b7f3e1a9c2d5
Revises: a1c4f9d7e2b8
Create Date: 2026-09-12 09:00:00.000000

AI Operational Intelligence, Horizon 1 Stage 3 — the review queue an
(eventual) OMC rate-fetch cron proposes into, and staff accept/reject on
the Price List page. Unlike `tenant.price_list` (append-only — see that
migration's own docstring), this table is a real review queue: a row's
`status` moves `pending` → `accepted`/`rejected` in place, so the grant is
`SELECT, INSERT, UPDATE` — same shape as `compliance.compliance_document`
(`d2e3f4051a6c`), the other "written once, then reviewed" table in this
schema.

`branch_id` nullable + `UNIQUE NULLS NOT DISTINCT` on the historization
dimension mirrors `tenant.price_list` exactly, so a re-run of the monthly
fetch job for the same month is a harmless `ON CONFLICT DO NOTHING`, not a
duplicate proposal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "b7f3e1a9c2d5"
down_revision: str | None = "a1c4f9d7e2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "price_list_proposal"


def _grant(*, privileges: str) -> str:
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
                    'GRANT {privileges} ON {_SCHEMA}.{_TABLE} TO %I', app_role
                );
            END IF;
        END
        $$;
    """


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey(f"{_SCHEMA}.tenant.id"), nullable=False),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("customer_type", sa.String(length=20), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey(f"{_SCHEMA}.branch.id"), nullable=True),
        sa.Column("proposed_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("proposed_price > 0", name="ck_price_list_proposal_price_positive"),
        sa.CheckConstraint(
            "customer_type IN ('domestic', 'commercial', 'industrial', 'government')",
            name="ck_price_list_proposal_customer_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_price_list_proposal_status",
        ),
        schema=_SCHEMA,
    )
    op.execute(f"""
        ALTER TABLE {_SCHEMA}.{_TABLE}
        ADD CONSTRAINT uq_price_list_proposal_dimension_effective
        UNIQUE NULLS NOT DISTINCT (
            tenant_id, cylinder_type_id, customer_type, branch_id, effective_from
        )
    """)
    op.create_index(
        "idx_price_list_proposal_tenant_status",
        _TABLE,
        ["tenant_id", "status"],
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
    op.execute(_grant(privileges="SELECT, INSERT, UPDATE"))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
