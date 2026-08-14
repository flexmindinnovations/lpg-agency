from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.application.reporting.ports import ReportingRepository
from lpg.application.reporting.queries.get_customer_consumption import GetCustomerConsumptionUseCase
from lpg.application.reporting.queries.get_daily_sales import GetDailySalesUseCase
from lpg.application.reporting.queries.get_driver_performance import GetDriverPerformanceUseCase
from lpg.application.reporting.queries.get_gst_report import GetGstReportUseCase
from lpg.infrastructure.persistence.repositories.reporting import SqlAlchemyReportingRepository


from collections.abc import AsyncIterator

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.application.common.ports import TenantContext


async def get_reporting_repository(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AsyncIterator[ReportingRepository]:
    from lpg.api.app import get_app_state

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    async for session in database.open_session(tenant_id=tenant_context.tenant_id):
        yield SqlAlchemyReportingRepository(session)


def get_daily_sales_use_case(
    reporting_repository: Annotated[ReportingRepository, Depends(get_reporting_repository)],
) -> GetDailySalesUseCase:
    return GetDailySalesUseCase(reporting_repository=reporting_repository)


def get_gst_report_use_case(
    reporting_repository: Annotated[ReportingRepository, Depends(get_reporting_repository)],
) -> GetGstReportUseCase:
    return GetGstReportUseCase(reporting_repository=reporting_repository)


def get_driver_performance_use_case(
    reporting_repository: Annotated[ReportingRepository, Depends(get_reporting_repository)],
) -> GetDriverPerformanceUseCase:
    return GetDriverPerformanceUseCase(reporting_repository=reporting_repository)


def get_customer_consumption_use_case(
    reporting_repository: Annotated[ReportingRepository, Depends(get_reporting_repository)],
) -> GetCustomerConsumptionUseCase:
    return GetCustomerConsumptionUseCase(reporting_repository=reporting_repository)
