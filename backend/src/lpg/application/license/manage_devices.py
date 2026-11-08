"""Linked-device management (ADR-071): a phone registers itself when its user
signs in, and the agency admin (`license:manage_tenant`) approves, blocks,
unblocks, renames, annotates or removes it. Own tenant only; every decision is
audited.

Side effects of a decision that outlive the transaction (dropping cached
status, ending the phone's sessions, telling the running app) are not done
here: the aggregate records a `DeviceStatusChanged` event and an
infrastructure handler reacts after the commit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import (
    DeviceLimitReachedError,
    DuplicateDeviceNameError,
    NotFoundError,
    TooManyWaitingDevicesError,
    ValidationError,
)
from lpg.domain.license.device_control import CONTROLLED_APP_TYPES, DeviceControlMode
from lpg.domain.license.linked_device import (
    MAX_DISPLAY_NAME_LENGTH,
    DeviceDetails,
    DeviceStatus,
    LinkedDevice,
    default_device_name,
    name_key,
)

if TYPE_CHECKING:
    from lpg.application.audit.ports import AuditLogEntry, AuditLogRepository, AuditTrail
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.license.ports import LicenseRepository, LinkedDeviceRepository
    from lpg.domain.license.license import License

#: Entity name used for every device audit row, explicit and generic alike.
AUDIT_ENTITY_NAME = "linked_device"
_AUDIT_ACTION_PREFIX = "device."

#: Most phones one login may have waiting for approval at once. A person has a
#: phone or two; more means a leaked login or a script, and each waiting phone
#: raises an alert for the agency admin.
MAX_WAITING_PER_USER = 5


# -- Registration (called when a phone signs in) -----------------------------------


@dataclass(frozen=True, slots=True)
class RegisterDeviceCommand(Command):
    tenant_id: uuid.UUID
    app_type: str
    #: SHA-256 of the install ID — the plain value never gets this far.
    device_identifier: str
    #: What the user typed, or `None`: the phone then gets `device_<ref>`.
    display_name: str | None
    details: DeviceDetails
    #: SHA-256 of the Android ID / iOS vendor ID, if the phone reported one.
    hardware_ref: str | None
    user_id: uuid.UUID | None
    user_name: str | None
    mode: DeviceControlMode


@dataclass(frozen=True, slots=True)
class DeviceRegistration:
    device: LinkedDevice
    #: True when this sign-in created the record or put a removed phone back
    #: in the queue — what the audit trail and the admin alert are about.
    is_new: bool


class RegisterDeviceUseCase:
    """Find or create the record for a phone that just signed in.

    A phone is recognised by its hardware reference first (the hashed Android
    ID / iOS vendor ID), then by its install ID. A known phone that comes back
    with a new install ID — the app was reinstalled or its data cleared — keeps
    its record, approval and name; only the install ID is replaced. So the same
    phone can never be listed twice in an agency, and is never asked for a
    name again.

    A first-time phone starts **pending** (it needs an admin's approval).
    The one exception is `observe` mode, whose job is to build the list
    without blocking anybody: the phone is recorded as **approved** while the
    plan still has seats, and pending once it does not. Never auto-evicts
    another device to make room.
    """

    def __init__(
        self,
        license_repository: LicenseRepository,
        device_repository: LinkedDeviceRepository,
        audit: AuditTrail,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._license_repository = license_repository
        self._device_repository = device_repository
        self._audit = audit
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterDeviceCommand) -> DeviceRegistration:
        if command.app_type not in CONTROLLED_APP_TYPES or not command.mode.records_devices:
            msg = "Devices are only recorded for the Driver and Admin apps, and not when off."
            raise ValidationError(msg, app_type=command.app_type)

        license_ = await self._license_repository.get_by_tenant_id(command.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        now = datetime.now(UTC)
        existing = await self._find_existing(command)

        if existing is None:
            status = await self._starting_status(command, license_)
            await self._guard_waiting_queue(command, status)
            device_id = uuid.uuid4()
            typed = " ".join((command.display_name or "").split())
            name = unique_device_name(
                typed or default_device_name(command.hardware_ref or command.device_identifier),
                await self._device_repository.active_names(command.tenant_id),
            )
            device = LinkedDevice.register(
                device_id,
                command.tenant_id,
                license_.id,
                command.app_type,
                command.device_identifier,
                name,
                at=now,
                status=status,
                details=command.details,
                hardware_ref=command.hardware_ref,
                user_id=command.user_id,
                user_name=command.user_name,
                name_confirmed=bool(typed),
            )
            await self._device_repository.add(device)
            await self._audit_registered(device, command.mode)
            await self._unit_of_work.commit()
            return DeviceRegistration(device, is_new=True)

        is_new = False
        if existing.status is DeviceStatus.REMOVED:
            status = await self._starting_status(command, license_)
            await self._guard_waiting_queue(command, status)
            existing.reopen(status=status, at=now)
            taken = await self._device_repository.active_names(
                command.tenant_id, excluding=existing.id
            )
            if name_key(existing.display_name) in taken:
                existing.rename(unique_device_name(existing.display_name, taken))
            is_new = True
        existing.record_sign_in(
            at=now,
            user_id=command.user_id,
            user_name=command.user_name,
            details=command.details,
            hardware_ref=command.hardware_ref,
        )
        await self._device_repository.save(existing)
        if is_new:
            await self._audit_registered(existing, command.mode)
        await self._unit_of_work.commit()
        return DeviceRegistration(existing, is_new=is_new)

    async def _find_existing(self, command: RegisterDeviceCommand) -> LinkedDevice | None:
        by_install = await self._device_repository.get_by_identifier(
            command.tenant_id, command.app_type, command.device_identifier
        )
        if command.hardware_ref is None:
            return by_install
        by_hardware = await self._device_repository.get_by_hardware_ref(
            command.tenant_id, command.app_type, command.hardware_ref
        )
        if by_hardware is None:
            return by_install
        if by_install is None or by_install.id == by_hardware.id:
            # Same phone, new install ID (or nothing changed).
            by_hardware.rebind_identifier(command.device_identifier)
            return by_hardware
        # An older record for this install and a newer one for this hardware:
        # keep the install's record and retire the other, so the hardware link
        # stays one-to-one.
        if by_hardware.is_active:
            by_hardware.remove(by=None, at=datetime.now(UTC))
        by_hardware.release_hardware_ref()
        await self._device_repository.save(by_hardware)
        return by_install

    async def _guard_waiting_queue(
        self, command: RegisterDeviceCommand, status: DeviceStatus
    ) -> None:
        if status is not DeviceStatus.PENDING or command.user_id is None:
            return
        waiting = await self._device_repository.count_waiting_for_user(
            command.tenant_id, command.user_id
        )
        if waiting >= MAX_WAITING_PER_USER:
            msg = (
                "Too many phones from this login are waiting for approval. "
                "Ask your agency to approve or remove some."
            )
            raise TooManyWaitingDevicesError(msg, tenant_id=str(command.tenant_id))

    async def _starting_status(
        self, command: RegisterDeviceCommand, license_: License
    ) -> DeviceStatus:
        if command.mode is not DeviceControlMode.OBSERVE:
            return DeviceStatus.PENDING
        seats_used = await self._device_repository.count_with_status(
            command.tenant_id, DeviceStatus.APPROVED, app_type=command.app_type
        )
        if license_.is_within_device_limit(command.app_type, seats_used):
            return DeviceStatus.APPROVED
        return DeviceStatus.PENDING

    async def _audit_registered(self, device: LinkedDevice, mode: DeviceControlMode) -> None:
        await self._audit.record(
            action=f"{_AUDIT_ACTION_PREFIX}registered",
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(device.id),
            entity_display_name=device.display_name,
            details={"app_type": device.app_type, "mode": mode.value},
            after={"status": device.status.value},
        )


def unique_device_name(wanted: str, taken: set[str]) -> str:
    """`wanted`, or `wanted 2`, `wanted 3`… — the first one not in `taken`
    (a set of `name_key`s)."""
    base = " ".join(wanted.split())[:MAX_DISPLAY_NAME_LENGTH]
    if name_key(base) not in taken:
        return base
    counter = 2
    while True:
        suffix = f" {counter}"
        candidate = f"{base[: MAX_DISPLAY_NAME_LENGTH - len(suffix)]}{suffix}"
        if name_key(candidate) not in taken:
            return candidate
        counter += 1


async def require_name_free(
    repository: LinkedDeviceRepository, tenant_id: uuid.UUID, name: str, device_id: uuid.UUID
) -> None:
    """Refuse a name another phone in the agency already has, and suggest one."""
    taken = await repository.active_names(tenant_id, excluding=device_id)
    if name_key(name) in taken:
        suggestion = unique_device_name(name, taken)
        msg = f"Another phone already has the name '{name.strip()}'. Try '{suggestion}'."
        raise DuplicateDeviceNameError(msg, suggestion=suggestion)


# -- A phone naming itself ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NameOwnDeviceCommand(Command):
    tenant_id: uuid.UUID
    device_id: uuid.UUID
    name: str
    user_id: uuid.UUID | None = None


class NameOwnDeviceUseCase:
    """The name a phone's user picks once, right after the phone is first
    seen. Not an admin decision: allowed whatever state the phone is in."""

    def __init__(
        self, device_repository: LinkedDeviceRepository, audit: AuditTrail, unit_of_work: UnitOfWork
    ) -> None:
        self._device_repository = device_repository
        self._audit = audit
        self._unit_of_work = unit_of_work

    async def execute(self, command: NameOwnDeviceCommand) -> LinkedDevice:
        device = await _load_device(self._device_repository, command.tenant_id, command.device_id)
        if not device.is_active:
            msg = "This phone was removed. Sign in again to register it."
            raise ValidationError(msg, device_id=str(device.id))
        old_name = device.display_name
        await require_name_free(self._device_repository, command.tenant_id, command.name, device.id)
        device.rename(command.name)
        await self._device_repository.save(device)
        await self._audit.record(
            action=f"{_AUDIT_ACTION_PREFIX}named",
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(device.id),
            entity_display_name=device.display_name,
            details={"app_type": device.app_type},
            before={"display_name": old_name},
            after={"display_name": device.display_name},
        )
        await self._unit_of_work.commit()
        return device


# -- Admin decisions ----------------------------------------------------------------


class DeviceAction(StrEnum):
    APPROVE = "approve"
    BLOCK = "block"
    UNBLOCK = "unblock"
    REMOVE = "remove"


_AUDIT_ACTION = {
    DeviceAction.APPROVE: "approved",
    DeviceAction.BLOCK: "blocked",
    DeviceAction.UNBLOCK: "unblocked",
    DeviceAction.REMOVE: "removed",
}
#: Actions that give a phone (back) a seat on the plan.
_SEAT_TAKING = frozenset({DeviceAction.APPROVE, DeviceAction.UNBLOCK})


@dataclass(frozen=True, slots=True)
class ChangeDeviceStatusCommand(Command):
    tenant_id: uuid.UUID
    device_id: uuid.UUID
    actor_id: uuid.UUID | None
    action: DeviceAction


class ChangeDeviceStatusUseCase:
    """Approve, block, unblock or remove one device.

    Approving (or unblocking) takes a seat, so it is refused once the plan's
    `device_caps` limit for that app is reached — remove or block another
    phone first. Blocking and removing free the seat.
    """

    def __init__(
        self,
        license_repository: LicenseRepository,
        device_repository: LinkedDeviceRepository,
        audit: AuditTrail,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._license_repository = license_repository
        self._device_repository = device_repository
        self._audit = audit
        self._unit_of_work = unit_of_work

    async def execute(self, command: ChangeDeviceStatusCommand) -> LinkedDevice:
        device = await _load_device(self._device_repository, command.tenant_id, command.device_id)
        before = device.status
        now = datetime.now(UTC)

        if command.action in _SEAT_TAKING:
            await self._require_free_seat(device)

        match command.action:
            case DeviceAction.APPROVE:
                device.approve(by=command.actor_id, at=now)
            case DeviceAction.BLOCK:
                device.block(by=command.actor_id, at=now)
            case DeviceAction.UNBLOCK:
                device.unblock(by=command.actor_id, at=now)
            case DeviceAction.REMOVE:
                device.remove(by=command.actor_id, at=now)

        await self._device_repository.save(device)
        await self._audit.record(
            action=f"{_AUDIT_ACTION_PREFIX}{_AUDIT_ACTION[command.action]}",
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(device.id),
            entity_display_name=device.display_name,
            details={"app_type": device.app_type},
            before={"status": before.value},
            after={"status": device.status.value},
        )
        await self._unit_of_work.commit()
        return device

    async def _require_free_seat(self, device: LinkedDevice) -> None:
        license_ = await self._license_repository.get_by_tenant_id(device.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{device.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(device.tenant_id))
        seats_used = await self._device_repository.count_with_status(
            device.tenant_id, DeviceStatus.APPROVED, app_type=device.app_type
        )
        if not license_.is_within_device_limit(device.app_type, seats_used):
            msg = (
                f"The plan allows no more approved phones for the {device.app_type}. "
                "Block or remove another phone first."
            )
            raise DeviceLimitReachedError(msg, tenant_id=str(device.tenant_id))


@dataclass(frozen=True, slots=True)
class DeleteDeviceCommand(Command):
    tenant_id: uuid.UUID
    device_id: uuid.UUID
    actor_id: uuid.UUID | None


class DeleteDeviceUseCase:
    """Delete one phone's record for good, whatever its state.

    Its sessions end with it, and a phone that signs in again afterwards is
    treated as new. The audit trail keeps what was deleted (name, app, state).
    """

    def __init__(
        self,
        device_repository: LinkedDeviceRepository,
        audit: AuditTrail,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._device_repository = device_repository
        self._audit = audit
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteDeviceCommand) -> None:
        device = await _load_device(self._device_repository, command.tenant_id, command.device_id)
        device.delete()
        await self._audit.record(
            action=f"{_AUDIT_ACTION_PREFIX}deleted",
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(device.id),
            entity_display_name=device.display_name,
            details={"app_type": device.app_type},
            before={"status": device.status.value, "display_name": device.display_name},
        )
        await self._device_repository.delete(device)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class UpdateDeviceDetailsCommand(Command):
    tenant_id: uuid.UUID
    device_id: uuid.UUID
    actor_id: uuid.UUID | None
    display_name: str | None = None
    #: Only applied when `change_asset_note` is set, so an empty value can
    #: clear the note without being confused with "not provided".
    asset_note: str | None = None
    change_asset_note: bool = False


class UpdateDeviceDetailsUseCase:
    """Rename a device and/or set the IMEI / serial note the admin types in."""

    def __init__(
        self, device_repository: LinkedDeviceRepository, audit: AuditTrail, unit_of_work: UnitOfWork
    ) -> None:
        self._device_repository = device_repository
        self._audit = audit
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateDeviceDetailsCommand) -> LinkedDevice:
        device = await _load_device(self._device_repository, command.tenant_id, command.device_id)
        old_name = device.display_name

        if command.display_name is not None:
            await require_name_free(
                self._device_repository, device.tenant_id, command.display_name, device.id
            )
            device.rename(command.display_name)
        if command.change_asset_note:
            device.set_asset_note(command.asset_note)

        await self._device_repository.save(device)
        # The note is an identifier (IMEI / serial): record that it changed,
        # never what it said.
        await self._audit.record(
            action=f"{_AUDIT_ACTION_PREFIX}updated",
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(device.id),
            entity_display_name=device.display_name,
            details={"app_type": device.app_type, "note_changed": command.change_asset_note},
            before={"display_name": old_name},
            after={"display_name": device.display_name},
        )
        await self._unit_of_work.commit()
        return device


async def _load_device(
    repository: LinkedDeviceRepository, tenant_id: uuid.UUID, device_id: uuid.UUID
) -> LinkedDevice:
    device = await repository.get(device_id)
    # Row-level security already hides other tenants' rows; the explicit check
    # keeps the rule true even if a repository is ever used without it.
    if device is None or device.tenant_id != tenant_id:
        msg = f"No device '{device_id}' found for this tenant."
        raise NotFoundError(msg, device_id=str(device_id))
    return device


# -- Reads ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListLinkedDevicesQuery:
    tenant_id: uuid.UUID
    app_type: str | None = None
    status: DeviceStatus | None = None


class ListLinkedDevicesUseCase:
    def __init__(self, repository: LinkedDeviceRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListLinkedDevicesQuery) -> list[LinkedDevice]:
        return list(
            await self._repository.list_for_tenant(
                query.tenant_id, app_type=query.app_type, status=query.status
            )
        )


@dataclass(frozen=True, slots=True)
class CountPendingDevicesQuery:
    tenant_id: uuid.UUID


class CountPendingDevicesUseCase:
    """The number behind the sidebar badge."""

    def __init__(self, repository: LinkedDeviceRepository) -> None:
        self._repository = repository

    async def execute(self, query: CountPendingDevicesQuery) -> int:
        return await self._repository.count_with_status(query.tenant_id, DeviceStatus.PENDING)


@dataclass(frozen=True, slots=True)
class GetDeviceHistoryQuery:
    tenant_id: uuid.UUID
    device_id: uuid.UUID
    limit: int = 50


class GetDeviceHistoryUseCase:
    """Who did what to one device, newest first — from the audit trail."""

    def __init__(
        self, device_repository: LinkedDeviceRepository, audit_log: AuditLogRepository
    ) -> None:
        self._device_repository = device_repository
        self._audit_log = audit_log

    async def execute(self, query: GetDeviceHistoryQuery) -> list[AuditLogEntry]:
        await _load_device(self._device_repository, query.tenant_id, query.device_id)
        page = await self._audit_log.get_page(
            query.tenant_id,
            entity_name=AUDIT_ENTITY_NAME,
            entity_id=str(query.device_id),
            action_prefix=_AUDIT_ACTION_PREFIX,
            limit=query.limit,
        )
        return list(page.items)
