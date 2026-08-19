"""fix_mv_customer_consumption_transaction_type

Revision ID: 3dd09c061286
Revises: bdd1f778c21a
Create Date: 2026-08-19 21:29:23.452055

`rpt.mv_customer_consumption` (added in `bab6ab8f401f`) filtered on
`transaction_type = 'exchange'`, a value `domain/cylinder_ledger/
cylinder_ledger.py`'s `TRANSACTION_TYPES` frozenset has never actually
allowed (`delivery`, `collection`, `adjustment`, `initial_balance` only) —
found while seeding demo data for the Reports & Analytics page, since no
real write path could ever have populated this view. Refill cadence is a
delivery-to-delivery interval, so this recreates the view against
`transaction_type = 'delivery'` instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = '3dd09c061286'
down_revision: str | None = 'bdd1f778c21a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS rpt.mv_customer_consumption CASCADE"))
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW rpt.mv_customer_consumption AS
        WITH RankedDeliveries AS (
            SELECT
                lt.tenant_id,
                cl.customer_id,
                lt.performed_at as transaction_time,
                LAG(lt.performed_at) OVER (PARTITION BY lt.tenant_id, cl.customer_id ORDER BY lt.performed_at) as prev_time
            FROM cylinder_ledger.ledger_transaction lt
            JOIN cylinder_ledger.cylinder_ledger cl ON lt.cylinder_ledger_id = cl.id
            WHERE lt.transaction_type = 'delivery'
        )
        SELECT
            tenant_id,
            customer_id,
            AVG(EXTRACT(EPOCH FROM (transaction_time - prev_time))/86400.0) as avg_refill_interval_days
        FROM RankedDeliveries
        WHERE prev_time IS NOT NULL
        GROUP BY tenant_id, customer_id
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_mv_customer_consumption_tenant_customer
        ON rpt.mv_customer_consumption (tenant_id, customer_id)
    """))
    op.execute(sa.text("GRANT SELECT ON rpt.mv_customer_consumption TO lpg_app"))


def downgrade() -> None:
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS rpt.mv_customer_consumption CASCADE"))
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW rpt.mv_customer_consumption AS
        WITH RankedExchanges AS (
            SELECT
                lt.tenant_id,
                cl.customer_id,
                lt.performed_at as transaction_time,
                LAG(lt.performed_at) OVER (PARTITION BY lt.tenant_id, cl.customer_id ORDER BY lt.performed_at) as prev_time
            FROM cylinder_ledger.ledger_transaction lt
            JOIN cylinder_ledger.cylinder_ledger cl ON lt.cylinder_ledger_id = cl.id
            WHERE lt.transaction_type = 'exchange'
        )
        SELECT
            tenant_id,
            customer_id,
            AVG(EXTRACT(EPOCH FROM (transaction_time - prev_time))/86400.0) as avg_refill_interval_days
        FROM RankedExchanges
        WHERE prev_time IS NOT NULL
        GROUP BY tenant_id, customer_id
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_mv_customer_consumption_tenant_customer
        ON rpt.mv_customer_consumption (tenant_id, customer_id)
    """))
    op.execute(sa.text("GRANT SELECT ON rpt.mv_customer_consumption TO lpg_app"))
