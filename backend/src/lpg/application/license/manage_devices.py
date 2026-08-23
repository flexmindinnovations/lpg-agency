"""Linked-device management. `RegisterDeviceUseCase` has no caller in this
repository today — it's built so a future mobile-facing endpoint can use it;
the API contract exists ahead of the client. Revoke/List are `agency_admin`,
`license:manage_tenant`, own tenant only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import DeviceLimitReachedError, NotFoundError
from lpg.domain.license.linked_device import LinkedDevice

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.license.ports import LicenseRepository, LinkedDeviceRepository


@dataclass(frozen=True, slots=True)
class RegisterDeviceCommand(Command):
    tenant_id: uuid.UUID
    app_type: str
    device_identifier: str
    display_name: str


class RegisterDeviceUseCase:
    """Never auto-evicts an existing device to make room — a device beyond
    the cap is rejected outright; the caller must revoke one first."""

    def __init__(
        self,
        license_repository: LicenseRepository,
        device_repository: LinkedDeviceRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._license_repository = license_repository
        self._device_repository = device_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterDeviceCommand) -> LinkedDevice:
        license_ = await self._license_repository.get_by_tenant_id(command.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        existing = await self._device_repository.get_by_identifier(
            command.tenant_id, command.app_type, command.device_identifier
        )
        now = datetime.now(UTC)
        if existing is not None:
            existing.touch_last_seen(at=now)
            await self._device_repository.save(existing)
            await self._unit_of_work.commit()
            return existing

        current_count = await self._device_repository.count_active_for_app_type(
            command.tenant_id, command.app_type
        )
        if not license_.is_within_device_limit(command.app_type, current_count):
            msg = f"The device limit for '{command.app_type}' has been reached."
            raise DeviceLimitReachedError(msg, tenant_id=str(command.tenant_id))

        device = LinkedDevice(
            uuid.uuid4(),
            command.tenant_id,
            license_.id,
            command.app_type,
            command.device_identifier,
            command.display_name,
            now,
        )
        await self._device_repository.add(device)
        await self._unit_of_work.commit()
        return device


@dataclass(frozen=True, slots=True)
class RevokeDeviceCommand(Command):
    tenant_id: uuid.UUID
    device_id: uuid.UUID


class RevokeDeviceUseCase:
    def __init__(self, repository: LinkedDeviceRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RevokeDeviceCommand) -> None:
        device = await self._repository.get(command.device_id)
        if device is None or device.tenant_id != command.tenant_id:
            msg = f"No device '{command.device_id}' found for this tenant."
            raise NotFoundError(msg, device_id=str(command.device_id))

        device.revoke(at=datetime.now(UTC))

        await self._repository.save(device)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListLinkedDevicesQuery:
    tenant_id: uuid.UUID
    app_type: str | None = None


class ListLinkedDevicesUseCase:
    def __init__(self, repository: LinkedDeviceRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListLinkedDevicesQuery) -> list[LinkedDevice]:
        return list(
            await self._repository.list_for_tenant(query.tenant_id, app_type=query.app_type)
        )
