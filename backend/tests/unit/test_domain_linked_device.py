"""Unit tests for `LinkedDevice`'s approval states (ADR-071)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.license.device_control import DeviceControlMode
from lpg.domain.license.linked_device import (
    DeviceDetails,
    DevicePendingApproval,
    DeviceStatus,
    DeviceStatusChanged,
    LinkedDevice,
)

_TENANT = uuid.uuid4()
_ADMIN = uuid.uuid4()


def _device(status: DeviceStatus = DeviceStatus.PENDING) -> LinkedDevice:
    device = LinkedDevice.register(
        uuid.uuid4(),
        _TENANT,
        uuid.uuid4(),
        "driver_app",
        "a" * 64,
        "Ravi's phone",
        at=datetime.now(UTC),
        status=status,
        details=DeviceDetails(manufacturer="Xiaomi", model="Redmi 12"),
        hardware_ref="b" * 64,
        user_id=uuid.uuid4(),
        user_name="Ravi",
    )
    device.clear_events()
    return device


def test_a_new_pending_phone_announces_itself() -> None:
    device = LinkedDevice.register(
        uuid.uuid4(),
        _TENANT,
        uuid.uuid4(),
        "admin_app",
        "c" * 64,
        "Office tablet",
        at=datetime.now(UTC),
        status=DeviceStatus.PENDING,
        details=DeviceDetails(),
        hardware_ref=None,
        user_id=None,
        user_name=None,
    )

    assert [type(e) for e in device.events] == [DevicePendingApproval]


def test_a_phone_recorded_as_approved_does_not_raise_an_alert() -> None:
    device = LinkedDevice.register(
        uuid.uuid4(),
        _TENANT,
        uuid.uuid4(),
        "driver_app",
        "c" * 64,
        "Phone",
        at=datetime.now(UTC),
        status=DeviceStatus.APPROVED,
        details=DeviceDetails(),
        hardware_ref=None,
        user_id=None,
        user_name=None,
    )

    assert device.events == ()
    assert device.holds_seat is True


@pytest.mark.parametrize("status", [DeviceStatus.BLOCKED, DeviceStatus.REMOVED])
def test_a_new_phone_cannot_start_blocked_or_removed(status: DeviceStatus) -> None:
    with pytest.raises(InvariantViolation):
        LinkedDevice.register(
            uuid.uuid4(),
            _TENANT,
            uuid.uuid4(),
            "driver_app",
            "c" * 64,
            "Phone",
            at=datetime.now(UTC),
            status=status,
            details=DeviceDetails(),
            hardware_ref=None,
            user_id=None,
            user_name=None,
        )


def test_approve_moves_pending_to_approved_and_records_who() -> None:
    device = _device()

    device.approve(by=_ADMIN, at=datetime.now(UTC))

    assert device.status is DeviceStatus.APPROVED
    assert device.status_changed_by == _ADMIN
    [event] = device.events
    assert isinstance(event, DeviceStatusChanged)
    assert (event.old_status, event.new_status) == ("pending", "approved")


@pytest.mark.parametrize("status", [DeviceStatus.APPROVED, DeviceStatus.BLOCKED])
def test_only_a_waiting_phone_can_be_approved(status: DeviceStatus) -> None:
    device = _device()
    if status is DeviceStatus.APPROVED:
        device.approve(by=_ADMIN, at=datetime.now(UTC))
    else:
        device.block(by=_ADMIN, at=datetime.now(UTC))

    with pytest.raises(InvariantViolation):
        device.approve(by=_ADMIN, at=datetime.now(UTC))


def test_block_then_unblock_returns_to_approved() -> None:
    device = _device(DeviceStatus.APPROVED)

    device.block(by=_ADMIN, at=datetime.now(UTC))
    blocked_holds_seat = device.holds_seat

    device.unblock(by=_ADMIN, at=datetime.now(UTC))

    assert blocked_holds_seat is False
    assert device.holds_seat is True


def test_a_waiting_phone_can_be_blocked_outright() -> None:
    device = _device()

    device.block(by=_ADMIN, at=datetime.now(UTC))

    assert device.status is DeviceStatus.BLOCKED


def test_unblock_requires_a_blocked_phone() -> None:
    with pytest.raises(InvariantViolation):
        _device(DeviceStatus.APPROVED).unblock(by=_ADMIN, at=datetime.now(UTC))


def test_a_blocked_phone_cannot_be_blocked_again() -> None:
    device = _device(DeviceStatus.APPROVED)
    device.block(by=_ADMIN, at=datetime.now(UTC))

    with pytest.raises(InvariantViolation):
        device.block(by=_ADMIN, at=datetime.now(UTC))


@pytest.mark.parametrize(
    "status", [DeviceStatus.PENDING, DeviceStatus.APPROVED, DeviceStatus.BLOCKED]
)
def test_any_phone_in_use_can_be_removed(status: DeviceStatus) -> None:
    device = _device(DeviceStatus.APPROVED)
    if status is DeviceStatus.PENDING:
        device = _device()
    if status is DeviceStatus.BLOCKED:
        device.block(by=_ADMIN, at=datetime.now(UTC))

    device.remove(by=_ADMIN, at=datetime.now(UTC))

    assert device.status is DeviceStatus.REMOVED
    assert device.is_active is False
    assert device.revoked_at is not None


def test_a_removed_phone_cannot_be_changed_until_it_asks_again() -> None:
    device = _device(DeviceStatus.APPROVED)
    device.remove(by=_ADMIN, at=datetime.now(UTC))

    for action in (device.approve, device.block, device.unblock, device.remove):
        with pytest.raises(InvariantViolation):
            action(by=_ADMIN, at=datetime.now(UTC))


def test_a_removed_phone_signing_in_again_goes_back_to_pending_not_approved() -> None:
    device = _device(DeviceStatus.APPROVED)
    device.remove(by=_ADMIN, at=datetime.now(UTC))
    device.clear_events()

    device.reopen(status=DeviceStatus.PENDING, at=datetime.now(UTC))

    assert device.status is DeviceStatus.PENDING
    assert device.revoked_at is None
    assert any(isinstance(e, DevicePendingApproval) for e in device.events)


def test_reopen_is_only_for_removed_phones() -> None:
    with pytest.raises(InvariantViolation):
        _device().reopen(status=DeviceStatus.PENDING, at=datetime.now(UTC))


def test_rename_trims_and_rejects_blank() -> None:
    device = _device()

    device.rename("  Van 2   phone ")
    assert device.display_name == "Van 2 phone"

    with pytest.raises(InvariantViolation):
        device.rename("   ")


def test_asset_note_can_be_set_cleared_and_is_length_limited() -> None:
    device = _device()

    device.set_asset_note(" 356938035643809 ")
    assert device.asset_note == "356938035643809"

    device.set_asset_note("")
    assert not device.asset_note

    with pytest.raises(InvariantViolation):
        device.set_asset_note("x" * 65)


def test_sign_in_updates_user_and_details_but_not_the_status() -> None:
    device = _device(DeviceStatus.APPROVED)
    new_user = uuid.uuid4()

    device.record_sign_in(
        at=datetime.now(UTC),
        user_id=new_user,
        user_name="Meena",
        details=DeviceDetails(model="Redmi 13", app_version="1.4.0"),
        hardware_ref=None,
    )

    assert device.status is DeviceStatus.APPROVED
    assert device.last_user_id == new_user
    assert device.details.model == "Redmi 13"
    # A sign-in that reports no hardware ref keeps the one we already know.
    assert device.hardware_ref == "b" * 64


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("off", DeviceControlMode.OFF),
        ("observe", DeviceControlMode.OBSERVE),
        (" ENFORCE ", DeviceControlMode.ENFORCE),
        ("block-everything", DeviceControlMode.OFF),
        (None, DeviceControlMode.OFF),
        (True, DeviceControlMode.OFF),
    ],
)
def test_device_control_mode_reads_leniently_and_fails_to_off(
    raw: object, expected: DeviceControlMode
) -> None:
    assert DeviceControlMode.parse(raw) is expected


def test_device_control_mode_flags() -> None:
    assert not DeviceControlMode.OFF.records_devices
    assert DeviceControlMode.OBSERVE.records_devices
    assert not DeviceControlMode.OBSERVE.enforces
    assert DeviceControlMode.ENFORCE.enforces
    assert not DeviceControlMode.is_valid("nope")
