from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.reporting import (
    get_customer_consumption_use_case,
    get_daily_sales_use_case,
    get_driver_performance_use_case,
    get_gst_report_use_case,
    get_gstr1_report_use_case,
)
from lpg.api.v1.schemas.reporting import (
    CustomerConsumptionResponse,
    DailySalesResponse,
    DriverPerformanceResponse,
    GstFilingResponse,
    Gstr1B2csRowResponse,
    Gstr1HsnRowResponse,
    Gstr1InvoiceRowResponse,
    Gstr1ReportResponse,
    GstTaxTotalsResponse,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.reporting.queries.get_customer_consumption import (
    GetCustomerConsumptionQuery,
    GetCustomerConsumptionUseCase,
)
from lpg.application.reporting.queries.get_daily_sales import (
    GetDailySalesQuery,
    GetDailySalesUseCase,
)
from lpg.application.reporting.queries.get_driver_performance import (
    GetDriverPerformanceQuery,
    GetDriverPerformanceUseCase,
)
from lpg.application.reporting.queries.get_gst_report import (
    GetGstReportQuery,
    GetGstReportUseCase,
)
from lpg.application.reporting.queries.get_gstr1_report import (
    GetGstr1ReportQuery,
    GetGstr1ReportUseCase,
    Gstr1InvoiceRow,
    TaxTotals,
)

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.get("/sales", response_model=list[DailySalesResponse])
async def get_daily_sales(
    start_date: date,
    end_date: date,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetDailySalesUseCase, Depends(get_daily_sales_use_case)],
    branch_id: uuid.UUID | None = None,
) -> list[DailySalesResponse]:
    """Invoiced sales per branch per business day (IST), inclusive dates."""
    records = await use_case.execute(
        GetDailySalesQuery(
            tenant_id=principal.tenant_id,
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
        )
    )
    return [DailySalesResponse.model_validate(record) for record in records]


@router.get("/gst", response_model=list[GstFilingResponse])
async def get_gst_report(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetGstReportUseCase, Depends(get_gst_report_use_case)],
) -> list[GstFilingResponse]:
    records = await use_case.execute(GetGstReportQuery(tenant_id=principal.tenant_id))
    return [GstFilingResponse.model_validate(record) for record in records]


@router.get("/drivers", response_model=list[DriverPerformanceResponse])
async def get_driver_performance(
    start_date: date,
    end_date: date,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetDriverPerformanceUseCase, Depends(get_driver_performance_use_case)],
    branch_id: uuid.UUID | None = None,
) -> list[DriverPerformanceResponse]:
    """One row per driver per business day (IST): stops, deliveries,
    failures, and cash handed over against cash collected.
    """
    records = await use_case.execute(
        GetDriverPerformanceQuery(
            tenant_id=principal.tenant_id,
            start_date=start_date,
            end_date=end_date,
            branch_id=branch_id,
        )
    )
    return [
        DriverPerformanceResponse(
            driver_id=record.driver_id,
            driver_name=record.driver_name,
            employee_code=record.employee_code,
            branch_name=record.branch_name,
            date=record.date,
            total_stops=record.total_stops,
            delivered_stops=record.delivered_stops,
            failed_stops=record.failed_stops,
            cash_expected=record.cash_expected,
            cash_handed_over=record.cash_handed_over,
            cash_accuracy=(
                float(record.cash_handed_over / record.cash_expected)
                if record.cash_handed_over is not None and record.cash_expected > 0
                else None
            ),
        )
        for record in records
    ]


def _totals(totals: TaxTotals) -> GstTaxTotalsResponse:
    return GstTaxTotalsResponse(
        taxable_value=totals.taxable_value,
        cgst=totals.cgst,
        sgst=totals.sgst,
        igst=totals.igst,
        total_tax=totals.total_tax,
    )


def _invoice_row(row: Gstr1InvoiceRow) -> Gstr1InvoiceRowResponse:
    return Gstr1InvoiceRowResponse(
        invoice_id=row.invoice_id,
        invoice_number=row.invoice_number,
        invoice_date=row.invoice_date,
        customer_name=row.customer_name,
        customer_gstin=row.customer_gstin,
        invoice_value=row.invoice_value,
        place_of_supply=row.place_of_supply,
        rate_percent=row.rate_percent,
        totals=_totals(row.totals),
    )


@router.get("/gst/gstr1", response_model=Gstr1ReportResponse)
async def get_gstr1_report(
    start_date: date,
    end_date: date,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetGstr1ReportUseCase, Depends(get_gstr1_report_use_case)],
) -> Gstr1ReportResponse:
    """Outward supplies for `[start_date, end_date]` (IST) laid out like
    GSTR-1: B2B, B2C large, B2C small and the HSN summary, with taxable
    value and CGST/SGST/IGST.
    """
    report = await use_case.execute(
        GetGstr1ReportQuery(tenant_id=principal.tenant_id, start_date=start_date, end_date=end_date)
    )
    return Gstr1ReportResponse(
        start_date=report.start_date,
        end_date=report.end_date,
        invoice_count=report.invoice_count,
        b2b=[_invoice_row(row) for row in report.b2b],
        b2cl=[_invoice_row(row) for row in report.b2cl],
        b2cs=[
            Gstr1B2csRowResponse(
                place_of_supply=row.place_of_supply,
                rate_percent=row.rate_percent,
                totals=_totals(row.totals),
            )
            for row in report.b2cs
        ],
        hsn=[
            Gstr1HsnRowResponse(
                hsn_code=row.hsn_code,
                rate_percent=row.rate_percent,
                quantity=row.quantity,
                totals=_totals(row.totals),
            )
            for row in report.hsn
        ],
        totals=_totals(report.totals),
    )


@router.get("/consumption", response_model=list[CustomerConsumptionResponse])
async def get_customer_consumption(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetCustomerConsumptionUseCase, Depends(get_customer_consumption_use_case)],
) -> list[CustomerConsumptionResponse]:
    records = await use_case.execute(GetCustomerConsumptionQuery(tenant_id=principal.tenant_id))
    return [CustomerConsumptionResponse.model_validate(record) for record in records]
