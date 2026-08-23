from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from lpg.application.reporting.ports import (
    CustomerConsumptionRecord,
    DailySalesRecord,
    DriverPerformanceRecord,
    GstFilingRecord,
    OutstandingBalanceRecord,
    ReportingRepository,
)

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyReportingRepository(ReportingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_daily_sales(
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailySalesRecord]:
        stmt = sa.text("""
            SELECT sale_date, branch_id, total_invoices, total_revenue, total_tax
            FROM rpt.vw_daily_sales
            WHERE tenant_id = :tenant_id
              AND sale_date >= :start_date
              AND sale_date <= :end_date
            ORDER BY sale_date DESC
        """)
        result = await self._session.execute(
            stmt, {"tenant_id": tenant_id, "start_date": start_date, "end_date": end_date}
        )
        return [
            DailySalesRecord(
                sale_date=row.sale_date,
                branch_id=row.branch_id,
                total_invoices=row.total_invoices,
                total_revenue=row.total_revenue,
                total_tax=row.total_tax,
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
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DriverPerformanceRecord]:
        stmt = sa.text("""
            SELECT driver_id, date, total_stops, delivered_stops, cash_accuracy
            FROM rpt.mv_driver_performance_daily
            WHERE tenant_id = :tenant_id
              AND date >= :start_date
              AND date <= :end_date
            ORDER BY date DESC
        """)
        result = await self._session.execute(
            stmt, {"tenant_id": tenant_id, "start_date": start_date, "end_date": end_date}
        )
        return [
            DriverPerformanceRecord(
                driver_id=row.driver_id,
                date=row.date,
                total_stops=row.total_stops,
                delivered_stops=row.delivered_stops,
                cash_accuracy=float(row.cash_accuracy),
            )
            for row in result.all()
        ]
