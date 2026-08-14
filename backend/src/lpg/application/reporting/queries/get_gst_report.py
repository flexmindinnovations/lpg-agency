from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from lpg.application.reporting.ports import GstFilingRecord, ReportingRepository


@dataclass(frozen=True, slots=True)
class GetGstReportQuery:
    tenant_id: uuid.UUID


class GetGstReportUseCase:
    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetGstReportQuery) -> Sequence[GstFilingRecord]:
        return await self._reporting_repository.get_gst_filing_periods(tenant_id=query.tenant_id)
