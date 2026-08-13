"""add consumer number sequence and lpg subsidy id

Revision ID: d2e8f4a6c1b9
Revises: a1b2c3d4e5f6
Create Date: 2026-08-11 09:00:00.000000

Two additions, both tenant-scoped:

1. `customer.customer_number_sequence` — a per-tenant counter backing
   auto-generated Consumer Numbers (`CN-000001`, `CN-000002`, ...). Staff
   can still override the suggested value manually (needed when onboarding
   an existing customer who already has a legacy/paper Consumer Number) —
   see `docs/data/06-data-dictionary.md`'s "tenant-defined format" note.
   Advanced via `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`
   (`SqlAlchemyConsumerNumberSequence`), which serializes concurrent callers
   via Postgres's row-level lock on the upserted row — no naming collision
   even under concurrent registrations.

2. `customer.customer.lpg_subsidy_id` — the genuinely nationally-standardized
   17-digit LPG ID used across all Indian OMCs (Indane/Bharat Gas/HP Gas)
   for subsidy (PAHAL/DBTL), KYC, and bank/Aadhaar linking — distinct from
   `consumer_number`, which is the shorter, locally-assigned-by-the-agency
   number used for refill booking. Optional (not every tenant captures it
   yet), unique per tenant when present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "d2e8f4a6c1b9"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMA = "customer"

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
    # 1. Per-tenant consumer-number counter.
    op.create_table(
        "customer_number_sequence",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenant.tenant.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default=sa.text("1")),
        schema=_SCHEMA,
    )
    op.execute(f"ALTER TABLE {_SCHEMA}.customer_number_sequence ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.customer_number_sequence FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{_SCHEMA}_customer_number_sequence_isolation
        ON {_SCHEMA}.customer_number_sequence
        USING ({_TENANT_RLS_PREDICATE})
    """)
    op.execute(_grant(table="customer_number_sequence", privileges="SELECT, INSERT, UPDATE"))

    # 2. The genuinely-standardized 17-digit LPG ID, distinct from
    # consumer_number (see module docstring).
    op.add_column(
        "customer",
        sa.Column("lpg_subsidy_id", sa.String(length=17), nullable=True),
        schema=_SCHEMA,
    )
    op.create_check_constraint(
        "chk_customer_lpg_subsidy_id_format",
        "customer",
        "lpg_subsidy_id IS NULL OR lpg_subsidy_id ~ '^[0-9]{17}$'",
        schema=_SCHEMA,
    )
    op.create_index(
        "uq_customer_tenant_lpg_subsidy_id",
        "customer",
        ["tenant_id", "lpg_subsidy_id"],
        unique=True,
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("uq_customer_tenant_lpg_subsidy_id", table_name="customer", schema=_SCHEMA)
    op.drop_constraint(
        "chk_customer_lpg_subsidy_id_format", "customer", schema=_SCHEMA, type_="check"
    )
    op.drop_column("customer", "lpg_subsidy_id", schema=_SCHEMA)

    op.execute(
        f"DROP POLICY IF EXISTS rls_{_SCHEMA}_customer_number_sequence_isolation "
        f"ON {_SCHEMA}.customer_number_sequence"
    )
    op.drop_table("customer_number_sequence", schema=_SCHEMA)
