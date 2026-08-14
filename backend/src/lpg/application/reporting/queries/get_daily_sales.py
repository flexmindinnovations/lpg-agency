from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from lpg.application.reporting.ports import DailySalesRecord, ReportingRepository


@dataclass(frozen=True, slots=True)
class GetDailySalesQuery:
    tenant_id: uuid.UUID
    start_date: date
    end_date: date


class GetDailySalesUseCase:
    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetDailySalesQuery) -> Sequence[DailySalesRecord]:
        return await self._reporting_repository.get_daily_sales(
            tenant_id=query.tenant_id,
            start_date=query.start_date,
            end_date=query.end_date,
        )
