from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import date

    from lpg.application.reporting.ports import DriverPerformanceRecord, ReportingRepository


@dataclass(frozen=True, slots=True)
class GetDriverPerformanceQuery:
    tenant_id: uuid.UUID
    start_date: date
    end_date: date


class GetDriverPerformanceUseCase:
    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetDriverPerformanceQuery) -> Sequence[DriverPerformanceRecord]:
        return await self._reporting_repository.get_driver_performance(
            tenant_id=query.tenant_id,
            start_date=query.start_date,
            end_date=query.end_date,
        )
