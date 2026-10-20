from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import ValidationError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import date

    from lpg.application.reporting.ports import DailySalesRecord, ReportingRepository


@dataclass(frozen=True, slots=True)
class GetDailySalesQuery:
    tenant_id: uuid.UUID
    start_date: date
    end_date: date
    branch_id: uuid.UUID | None = None


class GetDailySalesUseCase:
    """One row per branch per business day (IST)."""

    def __init__(self, reporting_repository: ReportingRepository) -> None:
        self._reporting_repository = reporting_repository

    async def execute(self, query: GetDailySalesQuery) -> Sequence[DailySalesRecord]:
        check_report_range(query.start_date, query.end_date)
        return await self._reporting_repository.get_daily_sales(
            tenant_id=query.tenant_id,
            start_date=query.start_date,
            end_date=query.end_date,
            branch_id=query.branch_id,
        )


#: A year of daily rows is the most a screen or export needs.
MAX_REPORT_RANGE_DAYS = 366


def check_report_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        msg = "The end date is before the start date."
        raise ValidationError(msg, errors={"end_date": [msg]})
    if (end_date - start_date).days > MAX_REPORT_RANGE_DAYS:
        msg = "Choose a range of at most one year."
        raise ValidationError(msg, errors={"start_date": [msg]})
