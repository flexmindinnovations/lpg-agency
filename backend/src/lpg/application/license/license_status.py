"""No permission gate — any authenticated principal's client needs to know
its own tenant's license status, the same reasoning
`IsFeatureFlagEnabledUseCase` already applies to flag status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from lpg.application.license.ports import LicenseRepository, LicenseStatusChecker


@dataclass(frozen=True, slots=True)
class LicenseStatusResult:
    status: LicenseLifecycleState
    plan_tier: str | None
    key_prefix: str | None
    activated_at: datetime | None
    expires_at: datetime | None
    grace_ends_at: datetime | None


@dataclass(frozen=True, slots=True)
class GetLicenseStatusQuery:
    tenant_id: uuid.UUID


class GetLicenseStatusUseCase:
    def __init__(
        self, status_checker: LicenseStatusChecker, repository: LicenseRepository
    ) -> None:
        self._status_checker = status_checker
        self._repository = repository

    async def execute(self, query: GetLicenseStatusQuery) -> LicenseStatusResult:
        status = await self._status_checker.get_status(query.tenant_id)
        license_ = await self._repository.get_by_tenant_id(query.tenant_id)
        if license_ is None:
            return LicenseStatusResult(
                status=LicenseLifecycleState.PENDING_ACTIVATION,
                plan_tier=None,
                key_prefix=None,
                activated_at=None,
                expires_at=None,
                grace_ends_at=None,
            )

        return LicenseStatusResult(
            status=status,
            plan_tier=license_.plan_tier,
            key_prefix=license_.key_prefix,
            activated_at=license_.activated_at,
            expires_at=license_.expires_at,
            grace_ends_at=license_.grace_ends_at,
        )
