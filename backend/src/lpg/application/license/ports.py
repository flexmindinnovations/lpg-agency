"""`license` bounded-context ports — one repository per aggregate root,
matching every other bounded context's shape (`03-backend-architecture.md`
§4), plus `LicenseStatusChecker`: a narrower, cache-backed read seam used by
`LoginUseCase`/`RefreshTokenUseCase`/`JwtTenantResolver` so those
per-request-critical call sites never depend on the full repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.license.license import (
        License,
        LicenseFeatureOverride,
        LicenseLifecycleState,
    )
    from lpg.domain.license.linked_device import LinkedDevice


@runtime_checkable
class LicenseRepository(Protocol):
    async def get(self, license_id: uuid.UUID) -> License | None: ...

    async def get_by_tenant_id(self, tenant_id: uuid.UUID) -> License | None: ...

    async def list_all(self) -> Sequence[License]: ...

    async def add(self, license: License) -> None: ...

    async def save(self, license: License) -> None: ...


@runtime_checkable
class LicenseFeatureOverrideRepository(Protocol):
    async def get_for_license_and_feature(
        self, license_id: uuid.UUID, feature_key: str
    ) -> LicenseFeatureOverride | None: ...

    async def list_for_license(
        self, license_id: uuid.UUID
    ) -> Sequence[LicenseFeatureOverride]: ...

    async def add(self, override: LicenseFeatureOverride) -> None: ...

    async def save(self, override: LicenseFeatureOverride) -> None: ...


@runtime_checkable
class LinkedDeviceRepository(Protocol):
    async def get(self, device_id: uuid.UUID) -> LinkedDevice | None: ...

    async def get_by_identifier(
        self, tenant_id: uuid.UUID, app_type: str, device_identifier: str
    ) -> LinkedDevice | None: ...

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, app_type: str | None = None
    ) -> Sequence[LinkedDevice]: ...

    async def count_active_for_app_type(self, tenant_id: uuid.UUID, app_type: str) -> int: ...

    async def add(self, device: LinkedDevice) -> None: ...

    async def save(self, device: LinkedDevice) -> None: ...


@runtime_checkable
class LicenseStatusChecker(Protocol):
    """The cheap, cached read `LoginUseCase`/`RefreshTokenUseCase`/
    `JwtTenantResolver` depend on — never the full `LicenseRepository`,
    since `JwtTenantResolver`'s use of this runs on every authenticated
    request.
    """

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState: ...

    async def invalidate(self, tenant_id: uuid.UUID) -> None: ...
