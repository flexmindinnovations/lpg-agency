"""create tenant.price_list table with RLS

Revision ID: f6b2d8e4a0c7
Revises: e5a1c7d3f9b2
Create Date: 2026-08-10 17:20:00.000000

Pricing gets its own dedicated table rather than living inside
`tenant_configuration`'s jsonb blob (decided ahead of this plan, see
`planning/features/07-administration-tenant-master-data/PLAN.md`) — pricing
has a real lookup dimension (cylinder type x customer type x optional
branch) Order Management (Phase 10) will query directly, unlike a scalar tax
rate. Append-only, same historization pattern as `tenant_configuration`:
"changing" a price means inserting a new row with a later `effective_from`.

`branch_id` is nullable — `NULL` means a tenant-wide default price; a
non-null value overrides it for that one branch. `UNIQUE NULLS NOT DISTINCT`
(PostgreSQL 15+) is what makes that actually enforce "one tenant-wide
default per (cylinder_type, customer_type, effective_from)" — plain `UNIQUE`
would let PostgreSQL's normal NULL-is-never-equal-to-NULL semantics silently
allow duplicate tenant-wide rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "f6b2d8e4a0c7"
down_revision: str | None = "e5a1c7d3f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "tenant"
_TABLE = "price_list"


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
        sa.Column(
            "cylinder_type_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.cylinder_type.id"),
            nullable=False,
        ),
        sa.Column("customer_type", sa.String(length=20), nullable=False),
        sa.Column(
            "branch_id",
            sa.Uuid(),
            sa.ForeignKey(f"{_SCHEMA}.branch.id"),
            nullable=True,
        ),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("price > 0", name="ck_price_list_price_positive"),
        sa.CheckConstraint(
            "customer_type IN ('domestic', 'commercial', 'industrial', 'government')",
            name="ck_price_list_customer_type",
        ),
        schema=_SCHEMA,
    )
    op.execute(f"""
        ALTER TABLE {_SCHEMA}.{_TABLE}
        ADD CONSTRAINT uq_price_list_dimension_effective
        UNIQUE NULLS NOT DISTINCT (
            tenant_id, cylinder_type_id, customer_type, branch_id, effective_from
        )
    """)
    op.create_index(
        "idx_price_list_tenant_cylinder_customer",
        _TABLE,
        ["tenant_id", "cylinder_type_id", "customer_type"],
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
    op.execute(_grant(table=_TABLE, privileges="SELECT, INSERT"))


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{_SCHEMA}_{_TABLE}_isolation ON {_SCHEMA}.{_TABLE}")
    op.drop_table(_TABLE, schema=_SCHEMA)
