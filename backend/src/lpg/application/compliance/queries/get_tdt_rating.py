"""TDT (Targeted Delivery Time) star rating queries (Phase 20 subsystem 2).

Same shape as `application.reporting.queries.get_driver_performance`'s
frozen-dataclass-query + thin-use-case pattern, except these use cases do
real work — resolve tenant-configured, MDG-edition-stamped reference data,
fetch fulfillment records, then call the pure domain computation — rather
than a one-line passthrough to a materialized view. See
`domain.compliance.tdt_rating`'s module docstring for why this lives in
`compliance`, not `reporting`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)
from lpg.domain.compliance.tdt_rating import (
    TdtFineRule,
    TdtQuarterlyRating,
    TdtStarBand,
    compute_quarterly_rating,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.compliance.ports import TdtRatingRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository


def _to_bands(config_value: object) -> tuple[TdtStarBand, ...]:
    """`tdt_star_rating_bands`'s stored shape is `{"mdg_edition": "...",
    "bands": [{"stars": N, "max_days": N | null}, ...]}` — see
    `domain.tenant.tenant_configuration.RECOGNIZED_CONFIG_KEYS`'s own
    comment for the full shape contract."""
    if not isinstance(config_value, dict):
        return ()
    raw_bands = config_value.get("bands")
    if not isinstance(raw_bands, list):
        return ()
    return tuple(
        TdtStarBand(stars=entry["stars"], max_days=entry["max_days"]) for entry in raw_bands
    )


def _to_fine_schedule(config_value: object) -> tuple[TdtFineRule, ...]:
    """`tdt_fine_schedule`'s stored shape is `{"mdg_edition": "...",
    "rules": [{"consecutive_low_quarters": N, "fine_percent": "X.XX"},
    ...]}`."""
    if not isinstance(config_value, dict):
        return ()
    raw_rules = config_value.get("rules")
    if not isinstance(raw_rules, list):
        return ()
    return tuple(
        TdtFineRule(
            consecutive_low_quarters=entry["consecutive_low_quarters"],
            fine_percent=Decimal(str(entry["fine_percent"])),
        )
        for entry in raw_rules
    )


def _current_quarter_bounds(today: date) -> tuple[date, date]:
    """Calendar quarter (Jan-Mar / Apr-Jun / Jul-Sep / Oct-Dec) as the
    default — the source plan's own open questions flag that whether the
    OMC actually uses the calendar quarter or the Indian financial-year
    quarter (Apr-Jun / ...) is unconfirmed. `quarter_end` is the exclusive
    upper bound (the first day of the *next* quarter), matching
    `TdtRatingRepository.get_fulfillment_records`'s own `[start, end)`
    contract.
    """
    quarter_index = (today.month - 1) // 3  # 0-3
    start_month = quarter_index * 3 + 1
    quarter_start = date(today.year, start_month, 1)
    if quarter_index == 3:  # Oct-Dec, wraps to next year
        quarter_end = date(today.year + 1, 1, 1)
    else:
        quarter_end = date(today.year, start_month + 3, 1)
    return quarter_start, quarter_end


def _date_to_utc_datetime(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class GetQuarterlyTdtRatingQuery:
    """`quarter_start` is inclusive, `quarter_end` is the **exclusive**
    upper bound (the first day *after* the quarter) — pass the first day of
    the quarter after the one you want, not its last day, to avoid
    off-by-one ambiguity."""

    tenant_id: uuid.UUID
    quarter_start: date
    quarter_end: date
    branch_id: uuid.UUID | None = None


class GetQuarterlyTdtRatingUseCase:
    def __init__(
        self,
        tdt_repository: TdtRatingRepository,
        tenant_config_repository: TenantConfigurationRepository,
    ) -> None:
        self._tdt_repository = tdt_repository
        self._tenant_config_repository = tenant_config_repository

    async def execute(self, query: GetQuarterlyTdtRatingQuery) -> TdtQuarterlyRating:
        # Resolved as of the quarter's own end date, not "now" — a closed
        # quarter's rating stays reproducible even if the tenant updates
        # the band/fine config afterward, the entire point of
        # TenantConfiguration's effective_from historization.
        resolve_at = _date_to_utc_datetime(query.quarter_end)
        bands_config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=query.tenant_id, config_key="tdt_star_rating_bands", at=resolve_at
            )
        )
        bands = _to_bands(bands_config.config_value) if bands_config is not None else ()

        records = await self._tdt_repository.get_fulfillment_records(
            _date_to_utc_datetime(query.quarter_start),
            _date_to_utc_datetime(query.quarter_end),
            branch_id=query.branch_id,
        )
        order_days = [(record.delivered_at - record.booked_at).days for record in records]

        if not bands:
            # No tdt_star_rating_bands configured for this tenant yet — no
            # rating is computable, not a guessed default. Matches
            # TdtQuarterlyRating.overall_stars=None's own reasoning for an
            # empty period.
            return TdtQuarterlyRating(
                overall_stars=None, total_orders=len(order_days), distribution=()
            )

        return compute_quarterly_rating(order_days, bands)


@dataclass(frozen=True, slots=True)
class GetLiveTdtProjectionQuery:
    tenant_id: uuid.UUID
    branch_id: uuid.UUID | None = None


class GetLiveTdtProjectionUseCase:
    """Same computation as `GetQuarterlyTdtRatingUseCase`, scoped to the
    current, still-open calendar quarter instead of a caller-supplied one
    — "so the distributor can still act" per the source plan, rather than
    only finding out the rating once the quarter has already closed."""

    def __init__(
        self,
        tdt_repository: TdtRatingRepository,
        tenant_config_repository: TenantConfigurationRepository,
    ) -> None:
        self._quarterly_use_case = GetQuarterlyTdtRatingUseCase(
            tdt_repository, tenant_config_repository
        )

    async def execute(self, query: GetLiveTdtProjectionQuery) -> TdtQuarterlyRating:
        quarter_start, quarter_end = _current_quarter_bounds(datetime.now(UTC).date())
        return await self._quarterly_use_case.execute(
            GetQuarterlyTdtRatingQuery(
                tenant_id=query.tenant_id,
                quarter_start=quarter_start,
                quarter_end=quarter_end,
                branch_id=query.branch_id,
            )
        )
