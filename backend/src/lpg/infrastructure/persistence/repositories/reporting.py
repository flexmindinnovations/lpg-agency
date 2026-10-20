from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from lpg.application.reporting.ports import (
    CustomerConsumptionRecord,
    DailySalesRecord,
    DriverPerformanceRecord,
    GstFilingRecord,
    GstInvoiceLineRecord,
    OutstandingBalanceRecord,
    ReportingRepository,
)

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


#: Reports bucket by the agency's business day. The platform serves Indian
#: agencies only (D-06), so this is IST rather than a per-tenant setting.
_BUSINESS_TZ = "Asia/Kolkata"


class SqlAlchemyReportingRepository(ReportingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_daily_sales(
        self,
        tenant_id: uuid.UUID,
        start_date: date,
        end_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> list[DailySalesRecord]:
        # Live over the invoices (RLS-scoped session), not `rpt.vw_daily_
        # sales`: that view buckets by UTC date and has no branch name, so
        # an invoice issued after 18:30 UTC landed on the wrong Indian day.
        stmt = sa.text(f"""
            SELECT (i.issued_at AT TIME ZONE '{_BUSINESS_TZ}')::date AS sale_date,
                   o.branch_id, b.name AS branch_name,
                   COUNT(i.id) AS total_invoices,
                   SUM(i.subtotal) AS taxable_value,
                   SUM(i.tax_amount) AS total_tax,
                   SUM(i.total_amount) AS total_revenue
            FROM accounting.invoice i
            JOIN orders.order o ON o.id = i.order_id
            LEFT JOIN tenant.branch b ON b.id = o.branch_id
            WHERE i.tenant_id = :tenant_id
              AND i.status != 'cancelled'
              AND (i.issued_at AT TIME ZONE '{_BUSINESS_TZ}')::date
                  BETWEEN :start_date AND :end_date
              AND (CAST(:branch_id AS uuid) IS NULL OR o.branch_id = :branch_id)
            GROUP BY 1, o.branch_id, b.name
            ORDER BY 1 DESC, b.name
        """)  # noqa: S608 - `_BUSINESS_TZ` is a module constant, not input
        result = await self._session.execute(
            stmt,
            {
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
                "branch_id": branch_id,
            },
        )
        return [
            DailySalesRecord(
                sale_date=row.sale_date,
                branch_id=row.branch_id,
                branch_name=row.branch_name,
                total_invoices=row.total_invoices,
                taxable_value=row.taxable_value,
                total_tax=row.total_tax,
                total_revenue=row.total_revenue,
            )
            for row in result.all()
        ]

    async def get_outstanding_balances(
        self, tenant_id: uuid.UUID
    ) -> list[OutstandingBalanceRecord]:
        stmt = sa.text("""
            SELECT customer_id, outstanding_balance
            FROM rpt.vw_outstanding_balances
            WHERE tenant_id = :tenant_id
        """)
        result = await self._session.execute(stmt, {"tenant_id": tenant_id})
        return [
            OutstandingBalanceRecord(
                customer_id=row.customer_id,
                outstanding_balance=row.outstanding_balance,
            )
            for row in result.all()
        ]

    async def get_gst_filing_periods(self, tenant_id: uuid.UUID) -> list[GstFilingRecord]:
        stmt = sa.text("""
            SELECT filing_period, total_gst
            FROM rpt.mv_gst_filing_period
            WHERE tenant_id = :tenant_id
            ORDER BY filing_period DESC
        """)
        result = await self._session.execute(stmt, {"tenant_id": tenant_id})
        return [
            GstFilingRecord(
                filing_period=row.filing_period,
                total_gst=row.total_gst,
            )
            for row in result.all()
        ]

    async def get_customer_consumption(
        self, tenant_id: uuid.UUID
    ) -> list[CustomerConsumptionRecord]:
        # The materialized view only carries customer_id — joined live
        # against customer.customer for the display name rather than
        # baking it into the view, so a renamed customer shows correctly
        # without waiting on the next materialized-view refresh.
        stmt = sa.text("""
            SELECT mv.customer_id, c.full_name AS customer_name, mv.avg_refill_interval_days
            FROM rpt.mv_customer_consumption mv
            JOIN customer.customer c ON c.id = mv.customer_id
            WHERE mv.tenant_id = :tenant_id
        """)
        result = await self._session.execute(stmt, {"tenant_id": tenant_id})
        return [
            CustomerConsumptionRecord(
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                avg_refill_interval_days=float(row.avg_refill_interval_days),
            )
            for row in result.all()
        ]

    async def get_driver_performance(
        self,
        tenant_id: uuid.UUID,
        start_date: date,
        end_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> list[DriverPerformanceRecord]:
        # Live, not `rpt.mv_driver_performance_daily`: the view had no driver
        # name and a hardcoded cash accuracy of 1.0.
        stmt = sa.text(f"""
            WITH routes AS (
                SELECT r.id, r.driver_id,
                       (r.route_date AT TIME ZONE '{_BUSINESS_TZ}')::date AS day
                FROM delivery.route r
                WHERE r.tenant_id = :tenant_id
                  AND (r.route_date AT TIME ZONE '{_BUSINESS_TZ}')::date
                      BETWEEN :start_date AND :end_date
                  AND (CAST(:branch_id AS uuid) IS NULL OR r.branch_id = :branch_id)
            ),
            stops AS (
                SELECT rt.driver_id, rt.day,
                       COUNT(rs.id) AS total_stops,
                       COUNT(rs.id) FILTER (WHERE rs.status = 'delivered') AS delivered_stops,
                       COUNT(rs.id) FILTER (WHERE rs.status = 'failed') AS failed_stops,
                       COALESCE(SUM(pod.amount_collected)
                                FILTER (WHERE pod.payment_method = 'cash'), 0) AS cash_expected
                FROM routes rt
                JOIN delivery.route_stop rs ON rs.route_id = rt.id
                LEFT JOIN orders.proof_of_delivery pod ON pod.order_id = rs.order_id
                GROUP BY rt.driver_id, rt.day
            ),
            handed AS (
                SELECT rt.driver_id, rt.day, SUM(h.actual_amount) AS cash_handed_over
                FROM routes rt
                JOIN accounting.cash_handover h ON h.route_id = rt.id
                GROUP BY rt.driver_id, rt.day
            )
            SELECT s.driver_id, s.day AS date,
                   TRIM(e.first_name || ' ' || e.last_name) AS driver_name,
                   e.employee_code, b.name AS branch_name,
                   s.total_stops, s.delivered_stops, s.failed_stops, s.cash_expected,
                   hd.cash_handed_over
            FROM stops s
            JOIN delivery.driver d ON d.id = s.driver_id
            JOIN tenant.employee e ON e.id = d.employee_id
            LEFT JOIN tenant.branch b ON b.id = d.branch_id
            LEFT JOIN handed hd ON hd.driver_id = s.driver_id AND hd.day = s.day
            ORDER BY s.day DESC, driver_name
        """)  # noqa: S608 - `_BUSINESS_TZ` is a module constant, not input
        result = await self._session.execute(
            stmt,
            {
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
                "branch_id": branch_id,
            },
        )
        return [
            DriverPerformanceRecord(
                driver_id=row.driver_id,
                driver_name=row.driver_name,
                employee_code=row.employee_code,
                branch_name=row.branch_name,
                date=row.date,
                total_stops=row.total_stops,
                delivered_stops=row.delivered_stops,
                failed_stops=row.failed_stops,
                cash_expected=row.cash_expected,
                cash_handed_over=row.cash_handed_over,
            )
            for row in result.all()
        ]

    async def get_gst_invoice_lines(
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[GstInvoiceLineRecord]:
        stmt = sa.text(f"""
            SELECT i.id AS invoice_id, i.invoice_number, i.issued_at,
                   c.full_name AS customer_name, i.customer_gstin,
                   i.supplier_state_code, i.place_of_supply_state_code,
                   i.total_amount AS invoice_total,
                   COALESCE(l.hsn_code, ct.hsn_code) AS hsn_code, l.gst_rate_percent,
                   l.quantity, l.subtotal AS taxable_value, l.tax_amount
            FROM accounting.invoice i
            JOIN accounting.invoice_line l ON l.invoice_id = i.id
            JOIN customer.customer c ON c.id = i.customer_id
            LEFT JOIN tenant.cylinder_type ct ON ct.id = l.cylinder_type_id
            WHERE i.tenant_id = :tenant_id
              AND i.status != 'cancelled'
              AND (i.issued_at AT TIME ZONE '{_BUSINESS_TZ}')::date
                  BETWEEN :start_date AND :end_date
            ORDER BY i.issued_at, i.invoice_number, l.id
        """)  # noqa: S608 - `_BUSINESS_TZ` is a module constant, not input
        result = await self._session.execute(
            stmt, {"tenant_id": tenant_id, "start_date": start_date, "end_date": end_date}
        )
        return [
            GstInvoiceLineRecord(
                invoice_id=row.invoice_id,
                invoice_number=row.invoice_number,
                issued_at=row.issued_at,
                customer_name=row.customer_name,
                customer_gstin=row.customer_gstin,
                supplier_state_code=row.supplier_state_code,
                place_of_supply_state_code=row.place_of_supply_state_code,
                invoice_total=row.invoice_total,
                hsn_code=row.hsn_code,
                gst_rate_percent=row.gst_rate_percent,
                quantity=row.quantity,
                taxable_value=row.taxable_value,
                tax_amount=row.tax_amount,
            )
            for row in result.all()
        ]
