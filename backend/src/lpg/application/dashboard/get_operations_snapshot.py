"""`GetOperationsSnapshotUseCase` — what an agency office needs to see first
thing in the morning (DO-28): today's bookings and the live order pipeline,
deliveries done and failed today, cancellations waiting for a manager, open
complaints, cash still with drivers, low stock, and unpaid invoices.

A read model like `GetDashboardSummaryUseCase`; the counts come from one
`OperationsReader` query set. Sections the caller has no permission for are
left out (`None`) rather than shown as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal

    from lpg.application.tenant.ports import TenantConfigurationRepository

#: Payment terms when a tenant has not set `invoice_payment_terms_days`.
DEFAULT_PAYMENT_TERMS_DAYS = 30
_PAYMENT_TERMS_KEY = "invoice_payment_terms_days"


@dataclass(frozen=True, slots=True)
class OrderPipeline:
    bookings_today: int
    #: Orders currently in each open status (`booked` … `failed_delivery`).
    open_by_status: dict[str, int]
    delivered_today: int
    failed_today: int
    pending_cancellations: int


@dataclass(frozen=True, slots=True)
class InvoiceSnapshot:
    outstanding_count: int
    outstanding_amount: Decimal
    overdue_count: int
    overdue_amount: Decimal
    on_hold_count: int


@dataclass(frozen=True, slots=True)
class CashSnapshot:
    awaiting_handover: Decimal
    handovers_awaiting_review: int


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    orders: OrderPipeline
    open_complaints: int
    low_stock_count: int
    invoices: InvoiceSnapshot | None
    cash: CashSnapshot | None
    payment_terms_days: int


class OperationsReader(Protocol):
    async def order_pipeline(self, day_start: datetime) -> OrderPipeline: ...

    async def open_complaints(self) -> int: ...

    async def low_stock_count(self, tenant_id: uuid.UUID) -> int: ...

    async def invoice_snapshot(self, overdue_before: datetime) -> InvoiceSnapshot: ...

    async def cash_snapshot(self) -> CashSnapshot: ...


@dataclass(frozen=True, slots=True)
class GetOperationsSnapshotQuery:
    tenant_id: uuid.UUID
    #: Start of the agency's business day, timezone-aware.
    day_start: datetime
    include_invoices: bool
    include_cash: bool


class GetOperationsSnapshotUseCase:
    def __init__(
        self,
        reader: OperationsReader,
        tenant_config_repository: TenantConfigurationRepository,
    ) -> None:
        self._reader = reader
        self._tenant_config_repository = tenant_config_repository

    async def execute(self, query: GetOperationsSnapshotQuery) -> OperationsSnapshot:
        terms = await self._payment_terms_days(query.tenant_id)
        overdue_before = datetime.now(UTC) - timedelta(days=terms)
        return OperationsSnapshot(
            orders=await self._reader.order_pipeline(query.day_start),
            open_complaints=await self._reader.open_complaints(),
            low_stock_count=await self._reader.low_stock_count(query.tenant_id),
            invoices=(
                await self._reader.invoice_snapshot(overdue_before)
                if query.include_invoices
                else None
            ),
            cash=await self._reader.cash_snapshot() if query.include_cash else None,
            payment_terms_days=terms,
        )

    async def _payment_terms_days(self, tenant_id: uuid.UUID) -> int:
        entries = await self._tenant_config_repository.list_for_tenant_and_key(
            tenant_id, _PAYMENT_TERMS_KEY
        )
        resolved = TenantConfigurationResolver.resolve(
            entries, _PAYMENT_TERMS_KEY, datetime.now(UTC)
        )
        try:
            days = int(str(resolved.config_value)) if resolved is not None else 0
        except ValueError:
            days = 0
        return days if days > 0 else DEFAULT_PAYMENT_TERMS_DAYS
