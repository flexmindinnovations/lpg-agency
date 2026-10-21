"""`SqlAlchemyOperationsReader` — the Home dashboard's operations counts
(DO-28). Raw SQL across `orders`, `complaint`, `accounting`, `delivery` and
`inventory`, like `SqlAlchemyReportingRepository`; every table is under RLS
on this tenant-scoped session.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from lpg.application.dashboard.get_operations_snapshot import (
    CashSnapshot,
    InvoiceSnapshot,
    OrderPipeline,
)

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from lpg.application.accounting.ports import CashHandoverRepository, UninvoicedOrderReader
    from lpg.application.inventory.ports import ReorderPolicyRepository
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

#: Statuses an order can be waiting in — everything before a terminal one.
_OPEN_STATUSES = (
    "booked",
    "confirmed",
    "assigned",
    "ready_for_dispatch",
    "out_for_delivery",
    "failed_delivery",
)


class SqlAlchemyOperationsReader:
    def __init__(
        self,
        unit_of_work: SqlAlchemyUnitOfWork,
        *,
        reorder_policy_repository: ReorderPolicyRepository,
        cash_handover_repository: CashHandoverRepository,
        uninvoiced_order_reader: UninvoicedOrderReader,
    ) -> None:
        self._session = unit_of_work.session
        self._reorder_policy_repository = reorder_policy_repository
        self._cash_handover_repository = cash_handover_repository
        self._uninvoiced_order_reader = uninvoiced_order_reader

    async def order_pipeline(self, day_start: datetime) -> OrderPipeline:
        open_rows = await self._session.execute(
            text("""
                SELECT status, COUNT(*) AS n FROM orders.order
                WHERE is_deleted = false AND status = ANY(:statuses)
                GROUP BY status
            """),
            {"statuses": list(_OPEN_STATUSES)},
        )
        open_by_status = dict.fromkeys(_OPEN_STATUSES, 0)
        for row in open_rows:
            open_by_status[row.status] = int(row.n)

        today = (
            await self._session.execute(
                text("""
                    SELECT
                      (SELECT COUNT(*) FROM orders.order
                        WHERE is_deleted = false AND created_at >= :day_start) AS bookings,
                      (SELECT COUNT(DISTINCT order_id) FROM orders.order_status_history
                        WHERE to_status = 'delivered' AND changed_at >= :day_start) AS delivered,
                      (SELECT COUNT(DISTINCT order_id) FROM orders.order_status_history
                        WHERE to_status = 'failed_delivery' AND changed_at >= :day_start)
                        AS failed,
                      (SELECT COUNT(*) FROM orders.cancellation_record
                        WHERE approved_by IS NULL AND is_deleted = false) AS cancellations
                """),
                {"day_start": day_start},
            )
        ).one()
        return OrderPipeline(
            bookings_today=int(today.bookings),
            open_by_status=open_by_status,
            delivered_today=int(today.delivered),
            failed_today=int(today.failed),
            pending_cancellations=int(today.cancellations),
        )

    async def open_complaints(self) -> int:
        result = await self._session.scalar(
            text("""
                SELECT COUNT(*) FROM complaint.complaint
                WHERE LOWER(status) NOT IN ('resolved', 'closed')
            """)
        )
        return int(result or 0)

    async def low_stock_count(self, tenant_id: uuid.UUID) -> int:
        return len(await self._reorder_policy_repository.list_breached_for_tenant(tenant_id))

    async def invoice_snapshot(self, overdue_before: datetime) -> InvoiceSnapshot:
        row = (
            await self._session.execute(
                text("""
                    WITH open_invoices AS (
                        SELECT i.issued_at,
                               i.total_amount - COALESCE(
                                   (SELECT SUM(p.amount) FROM accounting.payment p
                                     WHERE p.invoice_id = i.id), 0) AS balance
                        FROM accounting.invoice i
                        WHERE i.status IN ('issued', 'partially_paid')
                    )
                    SELECT COUNT(*) AS n, COALESCE(SUM(balance), 0) AS amount,
                           COUNT(*) FILTER (WHERE issued_at < :overdue_before) AS overdue_n,
                           COALESCE(SUM(balance) FILTER (WHERE issued_at < :overdue_before), 0)
                             AS overdue_amount
                    FROM open_invoices WHERE balance > 0
                """),
                {"overdue_before": overdue_before},
            )
        ).one()
        on_hold = await self._uninvoiced_order_reader.list_uninvoiced(limit=1000)
        return InvoiceSnapshot(
            outstanding_count=int(row.n),
            outstanding_amount=Decimal(row.amount),
            overdue_count=int(row.overdue_n),
            overdue_amount=Decimal(row.overdue_amount),
            on_hold_count=len(on_hold),
        )

    async def cash_snapshot(self) -> CashSnapshot:
        pending_reviews = await self._session.scalar(
            text("""
                SELECT COUNT(*) FROM accounting.cash_handover h
                WHERE NOT EXISTS (
                    SELECT 1 FROM accounting.cash_handover_review r
                    WHERE r.cash_handover_id = h.id
                )
            """)
        )
        return CashSnapshot(
            awaiting_handover=await self._cash_handover_repository.cash_awaiting_handover(),
            handovers_awaiting_review=int(pending_reviews or 0),
        )
