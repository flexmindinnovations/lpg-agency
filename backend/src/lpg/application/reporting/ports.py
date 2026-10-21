from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import date, datetime
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DailySalesRecord:
    """One branch's invoiced sales on one business day (IST)."""

    sale_date: date
    branch_id: uuid.UUID | None
    branch_name: str | None
    total_invoices: int
    taxable_value: Decimal
    total_tax: Decimal
    total_revenue: Decimal


@dataclass(frozen=True, slots=True)
class OutstandingBalanceRecord:
    customer_id: uuid.UUID
    outstanding_balance: Decimal


@dataclass(frozen=True, slots=True)
class GstFilingRecord:
    filing_period: str
    total_gst: Decimal


@dataclass(frozen=True, slots=True)
class GstInvoiceLineRecord:
    """One invoice line with what a GSTR-1 return needs to know about it."""

    invoice_id: uuid.UUID
    invoice_number: str | None
    issued_at: datetime
    customer_name: str
    customer_gstin: str | None
    supplier_state_code: str | None
    place_of_supply_state_code: str | None
    invoice_total: Decimal
    hsn_code: str | None
    gst_rate_percent: Decimal | None
    quantity: int
    taxable_value: Decimal
    tax_amount: Decimal


@dataclass(frozen=True, slots=True)
class CustomerConsumptionRecord:
    customer_id: uuid.UUID
    customer_name: str
    avg_refill_interval_days: float


@dataclass(frozen=True, slots=True)
class DriverPerformanceRecord:
    """One driver's routes on one business day (IST)."""

    driver_id: uuid.UUID
    driver_name: str
    employee_code: str | None
    branch_name: str | None
    date: date
    total_stops: int
    delivered_stops: int
    failed_stops: int
    #: Cash the deliveries say was collected, and what the driver handed
    #: over for those routes (`None` while no handover is declared).
    cash_expected: Decimal
    cash_handed_over: Decimal | None


class ReportingRepository(ABC):
    @abstractmethod
    async def get_daily_sales(
        self,
        tenant_id: uuid.UUID,
        start_date: date,
        end_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> list[DailySalesRecord]: ...

    @abstractmethod
    async def get_outstanding_balances(
        self, tenant_id: uuid.UUID
    ) -> list[OutstandingBalanceRecord]: ...

    @abstractmethod
    async def get_gst_filing_periods(self, tenant_id: uuid.UUID) -> list[GstFilingRecord]: ...

    @abstractmethod
    async def get_gst_invoice_lines(
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[GstInvoiceLineRecord]:
        """Lines of every non-cancelled invoice issued in `[start_date,
        end_date]` (IST business days).
        """

    @abstractmethod
    async def get_customer_consumption(
        self, tenant_id: uuid.UUID
    ) -> list[CustomerConsumptionRecord]: ...

    @abstractmethod
    async def get_driver_performance(
        self,
        tenant_id: uuid.UUID,
        start_date: date,
        end_date: date,
        branch_id: uuid.UUID | None = None,
    ) -> list[DriverPerformanceRecord]: ...
