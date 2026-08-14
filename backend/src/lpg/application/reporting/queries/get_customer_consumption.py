from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from lpg.application.reporting.ports import CustomerConsumptionRecord, ReportingRepository


@dataclass(frozen=True, slots=True)
class GetCustomerConsumptionQuery:
    tenant_id: uuid.UUID


class GetCustomerConsumptionUseCase:
    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetCustomerConsumptionQuery) -> Sequence[CustomerConsumptionRecord]:
        return await self._reporting_repository.get_customer_consumption(tenant_id=query.tenant_id)
