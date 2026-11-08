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

    from lpg.application.license.device_access import DeviceAccess
    from lpg.application.license.manage_devices import (
        DeviceRegistration,
        NameOwnDeviceCommand,
        RegisterDeviceCommand,
    )
    from lpg.domain.license.device_control import DeviceControlMode
    from lpg.domain.license.license import (
        License,
        LicenseFeatureOverride,
        LicenseLifecycleState,
    )
    from lpg.domain.license.linked_device import DeviceStatus, LinkedDevice


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

    async def list_for_license(self, license_id: uuid.UUID) -> Sequence[LicenseFeatureOverride]: ...

    async def add(self, override: LicenseFeatureOverride) -> None: ...

    async def save(self, override: LicenseFeatureOverride) -> None: ...


@runtime_checkable
class LinkedDeviceRepository(Protocol):
    async def get(self, device_id: uuid.UUID) -> LinkedDevice | None: ...

    async def get_by_identifier(
        self, tenant_id: uuid.UUID, app_type: str, device_identifier: str
    ) -> LinkedDevice | None: ...

    async def get_by_hardware_ref(
        self, tenant_id: uuid.UUID, app_type: str, hardware_ref: str
    ) -> LinkedDevice | None:
        """The phone with this hardware reference (removed ones included —
        a removed phone that comes back is reopened, not duplicated)."""
        ...

    async def active_names(
        self, tenant_id: uuid.UUID, *, excluding: uuid.UUID | None = None
    ) -> set[str]:
        """`name_key` of every device name in use in the agency (removed
        devices do not hold their name)."""
        ...

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        app_type: str | None = None,
        status: DeviceStatus | None = None,
    ) -> Sequence[LinkedDevice]:
        """Newest first. `status=None` lists every device still in use, i.e.
        everything except removed ones; ask for `REMOVED` to see those."""
        ...

    async def count_with_status(
        self, tenant_id: uuid.UUID, status: DeviceStatus, app_type: str | None = None
    ) -> int: ...

    async def count_waiting_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Phones waiting for approval whose last sign-in was this user."""
        ...

    async def add(self, device: LinkedDevice) -> None: ...

    async def save(self, device: LinkedDevice) -> None: ...

    async def delete(self, device: LinkedDevice) -> None:
        """Remove the record for good. The phone's refresh tokens go with it
        (they reference it with `ON DELETE CASCADE`); its audit history stays."""
        ...


@runtime_checkable
class LicenseStatusChecker(Protocol):
    """The cheap, cached read `LoginUseCase`/`RefreshTokenUseCase`/
    `JwtTenantResolver` depend on — never the full `LicenseRepository`,
    since `JwtTenantResolver`'s use of this runs on every authenticated
    request.
    """

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState: ...

    async def invalidate(self, tenant_id: uuid.UUID) -> None: ...


@runtime_checkable
class DeviceControlModeReader(Protocol):
    """The agency's `device_control` mode, read through a short-lived cache —
    consulted on every Driver and Admin app request."""

    async def get(self, tenant_id: uuid.UUID) -> DeviceControlMode: ...

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        """Forget the cached mode — called when an admin changes it, so the
        new mode applies at once rather than within a minute."""
        ...


@runtime_checkable
class DeviceAccessReader(Protocol):
    """One phone's status and identifier hash, read through a short-lived
    cache that an admin decision clears at once."""

    async def get(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> DeviceAccess | None: ...

    async def invalidate(self, tenant_id: uuid.UUID, device_id: uuid.UUID) -> None: ...


@runtime_checkable
class DeviceRegistrar(Protocol):
    """Records a phone at sign-in. The caller has no tenant session yet (sign-in
    happens before any), so the implementation opens its own tenant-scoped
    transaction and runs `RegisterDeviceUseCase` in it."""

    async def register(self, command: RegisterDeviceCommand) -> DeviceRegistration: ...


@runtime_checkable
class DeviceNamer(Protocol):
    """Lets a phone name itself while it may still be waiting for approval
    (the normal request path refuses such phones), so it opens its own
    tenant-scoped transaction like `DeviceRegistrar`."""

    async def name(self, command: NameOwnDeviceCommand) -> LinkedDevice: ...
