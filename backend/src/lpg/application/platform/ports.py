"""`platform` bounded-context ports — one repository per aggregate root,
matching every other bounded context's shape (`03-backend-architecture.md`
§4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.platform.feature_flag import FeatureFlag, FeatureFlagOverride


@runtime_checkable
class FeatureFlagRepository(Protocol):
    async def get(self, key: str) -> FeatureFlag | None: ...

    async def list_all(self) -> Sequence[FeatureFlag]: ...

    async def add(self, flag: FeatureFlag) -> None: ...

    async def save(self, flag: FeatureFlag) -> None: ...


@runtime_checkable
class FeatureFlagOverrideRepository(Protocol):
    async def get_for_tenant_and_flag(
        self, tenant_id: uuid.UUID, flag_key: str
    ) -> FeatureFlagOverride | None: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[FeatureFlagOverride]: ...

    async def add(self, override: FeatureFlagOverride) -> None: ...

    async def save(self, override: FeatureFlagOverride) -> None: ...
