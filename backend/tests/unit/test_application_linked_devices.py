"""Use-case tests for linked-device registration and admin decisions (ADR-071),
with in-memory fakes — no database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from lpg.application.common.errors import DeviceLimitReachedError, NotFoundError, ValidationError
from lpg.application.license.manage_devices import (
    ChangeDeviceStatusCommand,
    ChangeDeviceStatusUseCase,
    CountPendingDevicesQuery,
    CountPendingDevicesUseCase,
    DeviceAction,
    ListLinkedDevicesQuery,
    ListLinkedDevicesUseCase,
    RegisterDeviceCommand,
    RegisterDeviceUseCase,
    UpdateDeviceDetailsCommand,
    UpdateDeviceDetailsUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.license.device_control import DeviceControlMode
from lpg.domain.license.license import License
from lpg.domain.license.linked_device import DeviceDetails, DeviceStatus, LinkedDevice

if TYPE_CHECKING:
    from collections.abc import Sequence

_TENANT = uuid.uuid4()
_OTHER_TENANT = uuid.uuid4()
_ADMIN = uuid.uuid4()
_USER = uuid.uuid4()


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def record(self, **entry: Any) -> None:
        self.entries.append(entry)


class FakeLicenses:
    def __init__(self, caps: dict[str, int | None] | None = None) -> None:
        self._license = License(
            uuid.uuid4(),
            _TENANT,
            "hash",
            "PFX",
            "premium",
            timedelta(days=365),
            datetime.now(UTC),
            device_caps=caps,
        )

    async def get_by_tenant_id(self, tenant_id: uuid.UUID) -> License | None:
        return self._license if tenant_id == _TENANT else None


class FakeDevices:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, LinkedDevice] = {}

    async def get(self, device_id: uuid.UUID) -> LinkedDevice | None:
        return self.rows.get(device_id)

    async def get_by_identifier(
        self, tenant_id: uuid.UUID, app_type: str, device_identifier: str
    ) -> LinkedDevice | None:
        for device in self.rows.values():
            if (device.tenant_id, device.app_type, device.device_identifier) == (
                tenant_id,
                app_type,
                device_identifier,
            ):
                return device
        return None

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, app_type: str | None = None, status: DeviceStatus | None = None
    ) -> Sequence[LinkedDevice]:
        return [
            d
            for d in self.rows.values()
            if d.tenant_id == tenant_id
            and (app_type is None or d.app_type == app_type)
            and (d.is_active if status is None else d.status is status)
        ]

    async def count_with_status(
        self, tenant_id: uuid.UUID, status: DeviceStatus, app_type: str | None = None
    ) -> int:
        return sum(
            1
            for d in self.rows.values()
            if d.tenant_id == tenant_id
            and d.status is status
            and (app_type is None or d.app_type == app_type)
        )

    async def add(self, device: LinkedDevice) -> None:
        self.rows[device.id] = device

    async def save(self, device: LinkedDevice) -> None:
        self.rows[device.id] = device


def _register_command(
    *,
    identifier: str = "id-1",
    app_type: str = "driver_app",
    mode: DeviceControlMode = DeviceControlMode.ENFORCE,
    user_name: str = "Ravi",
) -> RegisterDeviceCommand:
    return RegisterDeviceCommand(
        tenant_id=_TENANT,
        app_type=app_type,
        device_identifier=identifier,
        display_name="Redmi 12",
        details=DeviceDetails(manufacturer="Xiaomi", model="Redmi 12"),
        hardware_ref="hw",
        user_id=_USER,
        user_name=user_name,
        mode=mode,
    )


def _setup(caps: dict[str, int | None] | None = None) -> tuple[Any, ...]:
    devices, audit, uow = FakeDevices(), FakeAudit(), FakeUnitOfWork()
    licenses = FakeLicenses(caps)
    register = RegisterDeviceUseCase(licenses, devices, audit, uow)  # type: ignore[arg-type]
    change = ChangeDeviceStatusUseCase(licenses, devices, audit, uow)  # type: ignore[arg-type]
    return devices, audit, uow, register, change


async def _approved_device(devices: FakeDevices, identifier: str) -> LinkedDevice:
    device = LinkedDevice.register(
        uuid.uuid4(),
        _TENANT,
        uuid.uuid4(),
        "driver_app",
        identifier,
        identifier,
        at=datetime.now(UTC),
        status=DeviceStatus.APPROVED,
        details=DeviceDetails(),
        hardware_ref=None,
        user_id=None,
        user_name=None,
    )
    device.clear_events()
    await devices.add(device)
    return device


# -- Registration -------------------------------------------------------------------


async def test_enforce_mode_puts_a_new_phone_in_the_waiting_queue_and_audits_it() -> None:
    devices, audit, uow, register, _ = _setup()

    result = await register.execute(_register_command())

    assert result.is_new
    assert result.device.status is DeviceStatus.PENDING
    assert result.device.last_user_name == "Ravi"
    assert uow.commits == 1
    assert [e["action"] for e in audit.entries] == ["device.registered"]
    assert audit.entries[0]["after"] == {"status": "pending"}
    assert len(devices.rows) == 1


async def test_observe_mode_records_a_new_phone_as_approved_while_seats_remain() -> None:
    *_, register, _ = _setup({"driver_app": 2})

    first = await register.execute(
        _register_command(identifier="a", mode=DeviceControlMode.OBSERVE)
    )
    second = await register.execute(
        _register_command(identifier="b", mode=DeviceControlMode.OBSERVE)
    )
    third = await register.execute(
        _register_command(identifier="c", mode=DeviceControlMode.OBSERVE)
    )

    assert first.device.status is DeviceStatus.APPROVED
    assert second.device.status is DeviceStatus.APPROVED
    # The plan has two seats: the third is recorded, but waits for an admin.
    assert third.device.status is DeviceStatus.PENDING


async def test_observe_mode_ignores_seats_when_the_plan_has_no_limit() -> None:
    *_, register, _ = _setup({"admin_app": None})

    result = await register.execute(
        _register_command(app_type="admin_app", mode=DeviceControlMode.OBSERVE)
    )

    assert result.device.status is DeviceStatus.APPROVED


async def test_off_mode_records_nothing() -> None:
    devices, audit, _, register, _ = _setup()

    with pytest.raises(ValidationError):
        await register.execute(_register_command(mode=DeviceControlMode.OFF))

    assert devices.rows == {}
    assert audit.entries == []


@pytest.mark.parametrize("app_type", ["customer_app", "warehouse_app"])
async def test_only_driver_and_admin_apps_are_registered(app_type: str) -> None:
    devices, *_, register, _ = _setup()

    with pytest.raises(ValidationError):
        await register.execute(_register_command(app_type=app_type))

    assert devices.rows == {}


async def test_signing_in_again_updates_the_record_without_a_new_audit_entry() -> None:
    devices, audit, _, register, _ = _setup()
    first = await register.execute(_register_command())

    again = await register.execute(_register_command(user_name="Meena"))

    assert not again.is_new
    assert again.device.id == first.device.id
    assert again.device.last_user_name == "Meena"
    assert len(devices.rows) == 1
    assert len(audit.entries) == 1


async def test_signing_in_again_never_changes_the_approval_state() -> None:
    *_, register, change = _setup()
    first = await register.execute(_register_command())
    await change.execute(
        ChangeDeviceStatusCommand(_TENANT, first.device.id, _ADMIN, DeviceAction.BLOCK)
    )

    again = await register.execute(_register_command())

    assert again.device.status is DeviceStatus.BLOCKED


async def test_a_removed_phone_that_signs_in_again_waits_for_approval_again() -> None:
    _, audit, _, register, change = _setup()
    first = await register.execute(_register_command())
    await change.execute(
        ChangeDeviceStatusCommand(_TENANT, first.device.id, _ADMIN, DeviceAction.REMOVE)
    )

    again = await register.execute(_register_command())

    assert again.is_new
    assert again.device.id == first.device.id
    assert again.device.status is DeviceStatus.PENDING
    assert [e["action"] for e in audit.entries] == [
        "device.registered",
        "device.removed",
        "device.registered",
    ]


# -- Admin decisions ------------------------------------------------------------------


async def test_approve_block_unblock_remove_each_write_a_named_audit_entry() -> None:
    _, audit, _, register, change = _setup()
    device = (await register.execute(_register_command())).device
    audit.entries.clear()

    for action in (
        DeviceAction.APPROVE,
        DeviceAction.BLOCK,
        DeviceAction.UNBLOCK,
        DeviceAction.REMOVE,
    ):
        await change.execute(ChangeDeviceStatusCommand(_TENANT, device.id, _ADMIN, action))

    assert [e["action"] for e in audit.entries] == [
        "device.approved",
        "device.blocked",
        "device.unblocked",
        "device.removed",
    ]
    assert audit.entries[0]["before"] == {"status": "pending"}
    assert audit.entries[0]["after"] == {"status": "approved"}
    assert all(e["entity_name"] == "linked_device" for e in audit.entries)


async def test_approve_is_refused_when_the_plan_has_no_free_seat() -> None:
    devices, _, _, register, change = _setup({"driver_app": 1})
    await _approved_device(devices, "existing")
    waiting = (await register.execute(_register_command(identifier="new"))).device

    with pytest.raises(DeviceLimitReachedError):
        await change.execute(
            ChangeDeviceStatusCommand(_TENANT, waiting.id, _ADMIN, DeviceAction.APPROVE)
        )

    assert waiting.status is DeviceStatus.PENDING


async def test_blocking_frees_the_seat_and_unblocking_needs_one_again() -> None:
    devices, _, _, register, change = _setup({"driver_app": 1})
    first = await _approved_device(devices, "first")
    waiting = (await register.execute(_register_command(identifier="second"))).device

    await change.execute(ChangeDeviceStatusCommand(_TENANT, first.id, _ADMIN, DeviceAction.BLOCK))
    await change.execute(
        ChangeDeviceStatusCommand(_TENANT, waiting.id, _ADMIN, DeviceAction.APPROVE)
    )

    with pytest.raises(DeviceLimitReachedError):
        await change.execute(
            ChangeDeviceStatusCommand(_TENANT, first.id, _ADMIN, DeviceAction.UNBLOCK)
        )


async def test_seats_are_counted_per_app_type() -> None:
    devices, _, _, register, change = _setup({"driver_app": 1, "admin_app": None})
    await _approved_device(devices, "driver")
    admin = (await register.execute(_register_command(app_type="admin_app"))).device

    await change.execute(ChangeDeviceStatusCommand(_TENANT, admin.id, _ADMIN, DeviceAction.APPROVE))

    assert admin.status is DeviceStatus.APPROVED


async def test_blocking_and_removing_are_never_refused_by_the_seat_limit() -> None:
    devices, _, _, _, change = _setup({"driver_app": 0})
    device = await _approved_device(devices, "x")

    await change.execute(ChangeDeviceStatusCommand(_TENANT, device.id, _ADMIN, DeviceAction.BLOCK))

    assert device.status is DeviceStatus.BLOCKED


async def test_an_invalid_move_is_refused_by_the_domain() -> None:
    devices, _, _, _, change = _setup()
    device = await _approved_device(devices, "x")

    with pytest.raises(InvariantViolation):
        await change.execute(
            ChangeDeviceStatusCommand(_TENANT, device.id, _ADMIN, DeviceAction.APPROVE)
        )


async def test_another_agencys_device_looks_like_it_does_not_exist() -> None:
    devices, _, _, _, change = _setup()
    foreign = await _approved_device(devices, "x")

    with pytest.raises(NotFoundError):
        await change.execute(
            ChangeDeviceStatusCommand(_OTHER_TENANT, foreign.id, _ADMIN, DeviceAction.BLOCK)
        )
    with pytest.raises(NotFoundError):
        await change.execute(
            ChangeDeviceStatusCommand(_TENANT, uuid.uuid4(), _ADMIN, DeviceAction.BLOCK)
        )

    assert foreign.status is DeviceStatus.APPROVED


async def test_rename_and_note_are_audited_without_the_note_text() -> None:
    devices, audit, uow, _, _ = _setup()
    device = await _approved_device(devices, "x")
    use_case = UpdateDeviceDetailsUseCase(devices, audit, uow)

    await use_case.execute(
        UpdateDeviceDetailsCommand(
            _TENANT,
            device.id,
            _ADMIN,
            display_name="Van 2",
            asset_note="IMEI 356938035643809",
            change_asset_note=True,
        )
    )

    assert device.display_name == "Van 2"
    assert device.asset_note == "IMEI 356938035643809"
    [entry] = audit.entries
    assert entry["action"] == "device.updated"
    assert entry["details"]["note_changed"] is True
    assert "356938035643809" not in repr(entry)


async def test_leaving_the_note_out_keeps_it_and_an_empty_note_clears_it() -> None:
    devices, audit, uow, _, _ = _setup()
    device = await _approved_device(devices, "x")
    use_case = UpdateDeviceDetailsUseCase(devices, audit, uow)
    await use_case.execute(
        UpdateDeviceDetailsCommand(
            _TENANT, device.id, _ADMIN, asset_note="S/N 1", change_asset_note=True
        )
    )

    await use_case.execute(UpdateDeviceDetailsCommand(_TENANT, device.id, _ADMIN, display_name="B"))
    assert device.asset_note == "S/N 1"

    await use_case.execute(
        UpdateDeviceDetailsCommand(
            _TENANT, device.id, _ADMIN, asset_note="", change_asset_note=True
        )
    )
    assert device.asset_note is None


# -- Reads ------------------------------------------------------------------------------


async def test_list_hides_removed_phones_unless_asked_and_filters_by_app() -> None:
    devices, _, _, _, change = _setup()
    keep = await _approved_device(devices, "keep")
    gone = await _approved_device(devices, "gone")
    await change.execute(ChangeDeviceStatusCommand(_TENANT, gone.id, _ADMIN, DeviceAction.REMOVE))
    list_devices = ListLinkedDevicesUseCase(devices)

    default = await list_devices.execute(ListLinkedDevicesQuery(_TENANT))
    removed = await list_devices.execute(
        ListLinkedDevicesQuery(_TENANT, status=DeviceStatus.REMOVED)
    )
    other_app = await list_devices.execute(ListLinkedDevicesQuery(_TENANT, app_type="admin_app"))

    assert [d.id for d in default] == [keep.id]
    assert [d.id for d in removed] == [gone.id]
    assert other_app == []


async def test_pending_count_only_counts_waiting_phones_of_this_agency() -> None:
    devices, _, _, register, _ = _setup()
    await _approved_device(devices, "approved")
    await register.execute(_register_command(identifier="w1"))
    await register.execute(_register_command(identifier="w2"))
    count = CountPendingDevicesUseCase(devices)

    assert await count.execute(CountPendingDevicesQuery(_TENANT)) == 2
    assert await count.execute(CountPendingDevicesQuery(_OTHER_TENANT)) == 0


# -- The `device_control` setting and the pending-phone alert ---------------------------


class _FakeConfigRepository:
    def __init__(self) -> None:
        self.added: list[Any] = []

    async def add(self, config: Any) -> None:
        self.added.append(config)


@pytest.mark.parametrize("mode", ["off", "observe", "enforce", " Observe "])
async def test_device_control_accepts_the_three_modes(mode: str) -> None:
    from lpg.application.tenant.tenant_configuration import (
        SetTenantConfigurationCommand,
        SetTenantConfigurationUseCase,
    )

    repository = _FakeConfigRepository()
    use_case = SetTenantConfigurationUseCase(repository, FakeUnitOfWork())  # type: ignore[arg-type]

    await use_case.execute(SetTenantConfigurationCommand(_TENANT, "device_control", mode))

    assert len(repository.added) == 1


@pytest.mark.parametrize("value", ["lockdown", "", None, True, 1])
async def test_device_control_rejects_anything_else_so_a_typo_cannot_lock_drivers_out(
    value: object,
) -> None:
    from lpg.application.tenant.tenant_configuration import (
        SetTenantConfigurationCommand,
        SetTenantConfigurationUseCase,
    )

    repository = _FakeConfigRepository()
    use_case = SetTenantConfigurationUseCase(repository, FakeUnitOfWork())  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await use_case.execute(SetTenantConfigurationCommand(_TENANT, "device_control", value))

    assert repository.added == []


def test_the_pending_phone_alert_reads_plainly_and_goes_to_agency_admins() -> None:
    from lpg.infrastructure.notification.catalog import Audience, spec_for
    from lpg.infrastructure.notification.event_catalog import definition_for

    spec = spec_for("device_pending_staff")

    assert spec is not None
    assert spec.audience is Audience.STAFF
    assert spec.permission == "license:manage_tenant"
    assert spec.push
    assert spec.body(
        {"device_name": "Ravi's Redmi", "app_label": "Driver app", "user_name": "Ravi"}
    ) == (
        "Ravi's Redmi (Driver app), signed in by Ravi, is waiting for you to approve or block it."
    )
    assert spec.body({}) == "A phone is waiting for you to approve or block it."
    assert definition_for("device_pending_staff") is not None
