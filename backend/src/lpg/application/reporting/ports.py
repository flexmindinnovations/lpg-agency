from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import date
    from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DailySalesRecord:
    sale_date: date
    branch_id: uuid.UUID | None
    total_invoices: int
    total_revenue: Decimal
    total_tax: Decimal


@dataclass(frozen=True, slots=True)
class OutstandingBalanceRecord:
    customer_id: uuid.UUID
    outstanding_balance: Decimal


@dataclass(frozen=True, slots=True)
class GstFilingRecord:
    filing_period: str
    total_gst: Decimal


@dataclass(frozen=True, slots=True)
class CustomerConsumptionRecord:
    customer_id: uuid.UUID
    customer_name: str
    avg_refill_interval_days: float


@dataclass(frozen=True, slots=True)
class DriverPerformanceRecord:
    driver_id: uuid.UUID
    date: date
    total_stops: int
    delivered_stops: int
    cash_accuracy: float


class ReportingRepository(ABC):
    @abstractmethod
    async def get_daily_sales(
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DailySalesRecord]: ...

    @abstractmethod
    async def get_outstanding_balances(
        self, tenant_id: uuid.UUID
    ) -> list[OutstandingBalanceRecord]: ...

    @abstractmethod
    async def get_gst_filing_periods(self, tenant_id: uuid.UUID) -> list[GstFilingRecord]: ...

    @abstractmethod
    async def get_customer_consumption(
        self, tenant_id: uuid.UUID
    ) -> list[CustomerConsumptionRecord]: ...

    @abstractmethod
    async def get_driver_performance(
        self, tenant_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DriverPerformanceRecord]: ...
