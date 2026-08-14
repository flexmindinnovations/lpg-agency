from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.reporting import (
    get_customer_consumption_use_case,
    get_daily_sales_use_case,
    get_driver_performance_use_case,
    get_gst_report_use_case,
)
from lpg.api.v1.schemas.reporting import (
    CustomerConsumptionResponse,
    DailySalesResponse,
    DriverPerformanceResponse,
    GstFilingResponse,
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

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.get("/sales", response_model=list[DailySalesResponse])
async def get_daily_sales(
    start_date: date,
    end_date: date,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetDailySalesUseCase, Depends(get_daily_sales_use_case)],
) -> list[DailySalesResponse]:
    records = await use_case.execute(
        GetDailySalesQuery(tenant_id=principal.tenant_id, start_date=start_date, end_date=end_date)
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
) -> list[DriverPerformanceResponse]:
    records = await use_case.execute(
        GetDriverPerformanceQuery(
            tenant_id=principal.tenant_id, start_date=start_date, end_date=end_date
        )
    )
    return [DriverPerformanceResponse.model_validate(record) for record in records]


@router.get("/consumption", response_model=list[CustomerConsumptionResponse])
async def get_customer_consumption(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetCustomerConsumptionUseCase, Depends(get_customer_consumption_use_case)],
) -> list[CustomerConsumptionResponse]:
    records = await use_case.execute(GetCustomerConsumptionQuery(tenant_id=principal.tenant_id))
    return [CustomerConsumptionResponse.model_validate(record) for record in records]
