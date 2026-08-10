"""`SqlAlchemyFeatureFlagRepository` — implements `FeatureFlagRepository`
(`lpg.application.platform.ports`).

Same repository shape as every other aggregate — constructed from a
`SqlAlchemyUnitOfWork`, registers loaded aggregates with it. `platform
.feature_flag` has no `tenant_id`/RLS, but reusing the tenant-scoped
session/`UnitOfWork` machinery anyway (rather than inventing a parallel
"platform-only" session mechanism) is harmless — RLS with no policy simply
never filters, and `SET LOCAL app.current_tenant_id` has no effect on a
table it was never applied to.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from lpg.domain.platform.feature_flag import FeatureFlag
from lpg.infrastructure.persistence.models.platform import FeatureFlagModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyFeatureFlagRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, key: str) -> FeatureFlag | None:
        row = await self._uow.session.get(FeatureFlagModel, key)
        if row is None:
            return None

        flag = self._to_domain(row)
        self._uow.register_aggregate(flag)
        return flag

    async def list_all(self) -> Sequence[FeatureFlag]:
        result = await self._uow.session.execute(
            select(FeatureFlagModel)
            .where(FeatureFlagModel.is_deleted.is_(False))
            .order_by(FeatureFlagModel.key)
        )
        return [self._to_domain(row) for row in result.scalars()]

    async def add(self, flag: FeatureFlag) -> None:
        self._uow.session.add(
            FeatureFlagModel(
                key=flag.key,
                description=flag.description,
                is_enabled_by_default=flag.is_enabled_by_default,
                rollout_percentage=flag.rollout_percentage,
                starts_at=flag.starts_at,
                ends_at=flag.ends_at,
            )
        )
        self._uow.register_aggregate(flag)

    async def save(self, flag: FeatureFlag) -> None:
        row = await self._uow.session.get(FeatureFlagModel, flag.key)
        if row is None:
            msg = f"Cannot save feature flag '{flag.key}' — no matching row was loaded."
            raise LookupError(msg)

        row.description = flag.description
        row.is_enabled_by_default = flag.is_enabled_by_default
        row.rollout_percentage = flag.rollout_percentage
        row.starts_at = flag.starts_at
        row.ends_at = flag.ends_at

    @staticmethod
    def _to_domain(row: FeatureFlagModel) -> FeatureFlag:
        return FeatureFlag(
            row.key,
            row.description,
            is_enabled_by_default=row.is_enabled_by_default,
            rollout_percentage=row.rollout_percentage,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            version=row.version,
        )
