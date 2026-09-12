"""create inventory.reorder_policy table with RLS

Revision ID: c4a8d6f2e9b3
Revises: b7f3e1a9c2d5
Create Date: 2026-09-12 11:00:00.000000

AI Operational Intelligence, Horizon 1 Stage 4 — admin-set reorder
thresholds per `(inventory_location, cylinder_type)`. Mutable, not
append-only (an admin edits a threshold in place; `SELECT, INSERT, UPDATE`
grant, same shape `4f8b2d6a9c1e` already uses for every other table in
this schema) — unlike `tenant.price_list`'s intentional historization,
there is no business reason to keep old threshold values around.

`last_reorder_notified_at` is the same dedupe-timestamp shape as
`orders.order.last_stale_notified_at` (`bc77a5343b06`) — guards the daily
`check_reorder_levels` cron against re-notifying on an overlapping/retried
run, not against a genuinely still-breached day re-notifying tomorrow.

v1 scope is warehouses only (`application/inventory/reorder.py`'s module
docstring) — a vehicle's load is transient/replenished from a warehouse,
not something you'd set a reorder point against — but the column is named
`inventory_location_id`, not `warehouse_id`, matching `inventory_balance`'s
own polymorphic shape rather than baking the v1 scoping choice into the
schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "c4a8d6f2e9b3"
down_revision: str | None = "b7f3e1a9c2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "inventory"
_TABLE = "reorder_policy"


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
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_location_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.inventory_location.id"),
            nullable=False,
        ),
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("reorder_point", sa.Integer(), nullable=False),
        sa.Column("safety_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reorder_notified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("reorder_point >= 0", name="ck_reorder_policy_point_nonnegative"),
        sa.CheckConstraint("safety_stock >= 0", name="ck_reorder_policy_safety_stock_nonnegative"),
        sa.UniqueConstraint(
            "tenant_id",
            "inventory_location_id",
            "cylinder_type_id",
            name="uq_reorder_policy_dimension",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_reorder_policy_tenant",
        _TABLE,
        ["tenant_id"],
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
