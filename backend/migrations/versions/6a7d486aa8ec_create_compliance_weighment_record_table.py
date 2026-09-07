"""create compliance weighment record table

Revision ID: 6a7d486aa8ec
Revises: d8b300ef303f
Create Date: 2026-09-07 18:00:00.000000

Delivers, for Weighment Part 2 (`planning/features/20-regulatory-compliance`
subsystem 1, MDG 2022 cl. 1.2(iv)/(1.4)(c)(d)):
  - `compliance.weighment_record` — append-only evidence that a cylinder
    weight check happened, either a 10% random sample at goods receipt
    (`context = 'goods_receipt_sample'`) or a 100% check before load-out
    (`context = 'load_out_full_check'`, the record Part 3's dispatch gate
    checks for). No standard audit columns (`created_at`/`updated_by`/etc.)
    — matches `inventory.inventory_transaction`'s precedent for append-only
    ledger rows: `GRANT SELECT, INSERT, UPDATE` then immediately
    `REVOKE UPDATE, DELETE` from the app role, enforcing append-only at the
    DB level, not just by convention.
  - No new permissions — `weighment:record` was already seeded in
    `d8b300ef303f` for exactly this table's endpoints.

`reference_id` is polymorphic (`grn` | `route`, per `reference_type`) — no
physical FK, same accepted-risk convention as `inventory.inventory_location.
location_ref_id` and `delivery.compliance_document.owner_id`, mitigated at
the application layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "6a7d486aa8ec"
down_revision: str | None = "d8b300ef303f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "compliance"
_TENANT_SCHEMA = "tenant"
_TABLE = "weighment_record"

_CONTEXTS = ("goods_receipt_sample", "load_out_full_check")
_REFERENCE_TYPES = ("grn", "route")
_RESULTS = ("pass", "fail")


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


def _revoke_mutation(*, table: str) -> str:
    """Append-only enforcement: the app role may SELECT/INSERT but never
    UPDATE/DELETE — matches `inventory.inventory_transaction`'s helper."""
    return f"""
        DO $$
        DECLARE
            app_role text := CASE current_database()
                WHEN 'lpg_uat' THEN 'lpg_app_uat'
                ELSE 'lpg_app'
            END;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_role) THEN
                EXECUTE format(
                    'REVOKE UPDATE, DELETE ON {_SCHEMA}.{table} FROM %I', app_role
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
            "tenant_id", sa.Uuid(), sa.ForeignKey(f"{_TENANT_SCHEMA}.tenant.id"), nullable=False
        ),
        sa.Column("scale_id", sa.Uuid(), sa.ForeignKey(f"{_SCHEMA}.scale.id"), nullable=False),
        sa.Column("context", sa.String(length=30), nullable=False),
        sa.Column("reference_type", sa.String(length=20), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_TENANT_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("total_cylinders_in_batch", sa.Integer(), nullable=False),
        sa.Column("cylinders_checked", sa.Integer(), nullable=False),
        sa.Column("underweight_cylinder_count", sa.Integer(), nullable=False),
        sa.Column("tolerance_grams_applied", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"context IN {_CONTEXTS}", name="ck_weighment_record_context"),
        sa.CheckConstraint(
            f"reference_type IN {_REFERENCE_TYPES}", name="ck_weighment_record_reference_type"
        ),
        sa.CheckConstraint(f"result IN {_RESULTS}", name="ck_weighment_record_result"),
        sa.CheckConstraint(
            "total_cylinders_in_batch > 0", name="ck_weighment_record_total_positive"
        ),
        sa.CheckConstraint(
            "cylinders_checked > 0 AND cylinders_checked <= total_cylinders_in_batch",
            name="ck_weighment_record_checked_range",
        ),
        sa.CheckConstraint(
            "underweight_cylinder_count >= 0 AND underweight_cylinder_count <= cylinders_checked",
            name="ck_weighment_record_underweight_range",
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "idx_weighment_record_reference",
        _TABLE,
        ["reference_type", "reference_id"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_weighment_record_tenant_recorded_at",
        _TABLE,
        ["tenant_id", "recorded_at"],
        schema=_SCHEMA,
    )

    _enable_rls(_TABLE)

    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT, UPDATE"))
    op.execute(_revoke_mutation(table=_TABLE))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
