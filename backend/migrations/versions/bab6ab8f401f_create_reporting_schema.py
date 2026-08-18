"""create_reporting_schema

Revision ID: bab6ab8f401f
Revises: b05967dbc83e
Create Date: 2026-08-14 18:16:21.476203

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = 'bab6ab8f401f'
down_revision: str | None = 'b05967dbc83e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Schema
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS rpt"))

    # 2. Daily Sales
    op.execute(sa.text("""
        CREATE VIEW rpt.vw_daily_sales AS
        SELECT 
            i.tenant_id,
            o.branch_id,
            DATE(i.issued_at AT TIME ZONE 'UTC') as sale_date,
            COUNT(i.id) as total_invoices,
            SUM(i.total_amount) as total_revenue,
            SUM(i.tax_amount) as total_tax
        FROM accounting.invoice i
        JOIN orders.order o ON i.order_id = o.id
        WHERE i.status != 'cancelled'
        GROUP BY i.tenant_id, o.branch_id, DATE(i.issued_at AT TIME ZONE 'UTC')
    """))

    # 3. Outstanding Balances
    op.execute(sa.text("""
        CREATE VIEW rpt.vw_outstanding_balances AS
        SELECT 
            i.tenant_id,
            i.customer_id,
            SUM(i.total_amount) as outstanding_balance
        FROM accounting.invoice i
        WHERE i.status = 'issued'
        GROUP BY i.tenant_id, i.customer_id
    """))

    # 4. GST Filing Period (Materialized View)
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW rpt.mv_gst_filing_period AS
        SELECT 
            tenant_id,
            TO_CHAR(issued_at AT TIME ZONE 'UTC', 'YYYY-MM') as filing_period,
            SUM(tax_amount) as total_gst
        FROM accounting.invoice
        WHERE status != 'cancelled'
        GROUP BY tenant_id, TO_CHAR(issued_at AT TIME ZONE 'UTC', 'YYYY-MM')
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_mv_gst_filing_period_tenant_period 
        ON rpt.mv_gst_filing_period (tenant_id, filing_period)
    """))

    # 5. Customer Consumption (Materialized View)
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

    # 6. Driver Performance Daily (Materialized View)
    op.execute(sa.text("""
        CREATE MATERIALIZED VIEW rpt.mv_driver_performance_daily AS
        SELECT
            r.tenant_id,
            r.driver_id,
            DATE(r.route_date AT TIME ZONE 'UTC') as date,
            COUNT(rs.id) as total_stops,
            SUM(CASE WHEN rs.status = 'delivered' THEN 1 ELSE 0 END) as delivered_stops,
            1.0 as cash_accuracy
        FROM delivery.route r
        JOIN delivery.route_stop rs ON rs.route_id = r.id
        GROUP BY r.tenant_id, r.driver_id, DATE(r.route_date AT TIME ZONE 'UTC')
    """))
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_mv_driver_perf_tenant_driver_date 
        ON rpt.mv_driver_performance_daily (tenant_id, driver_id, date)
    """))

    # 7. Grant access to application user
    op.execute(sa.text("GRANT USAGE ON SCHEMA rpt TO lpg_app"))
    op.execute(sa.text("GRANT SELECT ON ALL TABLES IN SCHEMA rpt TO lpg_app"))
    op.execute(sa.text("ALTER DEFAULT PRIVILEGES IN SCHEMA rpt GRANT SELECT ON TABLES TO lpg_app"))

def downgrade() -> None:
    # Drop in reverse order
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS rpt.mv_driver_performance_daily CASCADE"))
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS rpt.mv_customer_consumption CASCADE"))
    op.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS rpt.mv_gst_filing_period CASCADE"))
    op.execute(sa.text("DROP VIEW IF EXISTS rpt.vw_outstanding_balances CASCADE"))
    op.execute(sa.text("DROP VIEW IF EXISTS rpt.vw_daily_sales CASCADE"))
    op.execute(sa.text("DROP SCHEMA IF EXISTS rpt CASCADE"))
